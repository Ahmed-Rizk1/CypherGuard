"""
SecureNet SOC — Production ML Training Pipeline

Full training pipeline with:
- 12 aligned features (matching serving pipeline)
- StandardScaler preprocessing
- Model comparison: RandomForest vs XGBoost vs GradientBoosting vs LightGBM vs CatBoost
- 5-fold stratified cross-validation
- Model metadata + version tracking
- Saved as sklearn Pipeline (scaler + model in one artifact)
- Automatic experiment logging to PostgreSQL (MLflow-like)
- Automatic best model promotion to model_registry

Usage:
    python ml_engine/train_production.py [path_to_csv]

    Default CSV: Friday-WorkingHours-Afternoon-DDos.pcap_ISCX.csv
"""

import os
import sys
import json
import asyncio
import hashlib
import time
from datetime import datetime
from pathlib import Path

import pandas as pd
import numpy as np
from sklearn.ensemble import RandomForestClassifier, GradientBoostingClassifier
from sklearn.model_selection import StratifiedKFold, cross_val_score, cross_validate
from sklearn.preprocessing import StandardScaler
from sklearn.pipeline import Pipeline
from sklearn.metrics import (
    classification_report,
    accuracy_score,
    roc_auc_score,
    precision_score,
    recall_score,
    f1_score,
    confusion_matrix,
)
import joblib

# Optional: XGBoost
try:
    from xgboost import XGBClassifier

    HAS_XGBOOST = True
except ImportError:
    HAS_XGBOOST = False
    print("[!] XGBoost not installed. Install with: pip install xgboost")

# Optional: LightGBM
try:
    from lightgbm import LGBMClassifier

    HAS_LIGHTGBM = True
except ImportError:
    HAS_LIGHTGBM = False
    print("[!] LightGBM not installed. Install with: pip install lightgbm")

# Optional: CatBoost
try:
    from catboost import CatBoostClassifier

    HAS_CATBOOST = True
except ImportError:
    HAS_CATBOOST = False
    print("[!] CatBoost not installed. Install with: pip install catboost")

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from ml_engine.feature_engineering import FEATURE_COLUMNS, prepare_training_data
from shared.database import async_session, MLExperiment, ModelRegistry
from shared.drift_detector import DriftDetector


def _compute_model_hash(path: str) -> str:
    """Compute SHA256 hash of model file for integrity verification."""
    if not os.path.exists(path):
        return ""
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()


async def log_experiment_to_db(
    experiment_name: str,
    algorithm: str,
    hyperparameters: dict,
    dataset_name: str,
    dataset_rows: int,
    feature_count: int,
    accuracy: float,
    precision: float,
    recall: float,
    f1: float,
    roc_auc: float,
    cv_scores: dict,
    cv_mean: float,
    cv_std: float,
    confusion_matrix_data: dict,
    feature_importance_data: dict,
    model_file_path: str,
    training_time_seconds: float,
    notes: str = None,
) -> tuple:
    """
    Log ML experiment to database and auto-promote best model.

    Returns: (experiment_id, promoted_to_registry)
    """
    try:
        model_hash = _compute_model_hash(model_file_path)

        async with async_session() as session:
            # Check if this is the best model so far by F1 score
            from sqlalchemy import select, desc

            result = await session.execute(
                select(MLExperiment).order_by(desc(MLExperiment.f1_score)).limit(1)
            )
            best_existing = result.scalar()
            is_best = (best_existing is None) or (f1 > best_existing.f1_score)

            # Create experiment record
            experiment = MLExperiment(
                experiment_name=experiment_name,
                algorithm=algorithm,
                hyperparameters=hyperparameters,
                dataset_name=dataset_name,
                dataset_rows=dataset_rows,
                feature_count=feature_count,
                accuracy=accuracy,
                precision=precision,
                recall=recall,
                f1_score=f1,
                roc_auc=roc_auc,
                cv_scores=cv_scores,
                cv_mean=cv_mean,
                cv_std=cv_std,
                confusion_matrix=confusion_matrix_data,
                feature_importance=feature_importance_data,
                model_file_path=model_file_path,
                model_hash=model_hash,
                training_time_seconds=training_time_seconds,
                notes=notes,
                is_best=is_best,
                promoted_to_registry=False,
            )
            session.add(experiment)
            await session.flush()
            experiment_id = experiment.id

            # If best, promote to model_registry
            promoted = False
            if is_best:
                model_version = datetime.now().strftime("%Y%m%d_%H%M%S")
                registry_entry = ModelRegistry(
                    version=model_version,
                    algorithm=algorithm,
                    accuracy=accuracy,
                    f1_score=f1,
                    feature_columns={"features": FEATURE_COLUMNS},
                    training_samples=dataset_rows,
                    file_hash=model_hash,
                    is_active=True,
                )
                session.add(registry_entry)
                await session.flush()

                # Mark previous active models as inactive
                prev_active = await session.execute(
                    select(ModelRegistry).where(
                        ModelRegistry.is_active == True, ModelRegistry.id != registry_entry.id
                    )
                )
                for prev in prev_active.scalars():
                    prev.is_active = False

                experiment.promoted_to_registry = True
                experiment.registry_id = registry_entry.id
                promoted = True
                print(f"  ★ Promoted to model_registry (v{model_version})")

            await session.commit()
            return experiment_id, promoted

    except Exception as e:
        print(f"  [!] Experiment logging failed: {e}")
        return None, False


def train_and_evaluate(csv_path: str, output_dir: str = None) -> tuple:
    """
    Full training pipeline with cross-validation and model comparison.

    Args:
        csv_path: Path to CICIDS2017 CSV dataset.
        output_dir: Directory to save model artifacts. Defaults to ml_engine/models/.

    Returns:
        Tuple of (trained pipeline, metadata dict, experiment_id, promoted).
    """
    if output_dir is None:
        output_dir = os.path.join(os.path.dirname(__file__), "models")

    os.makedirs(output_dir, exist_ok=True)

    print("=" * 65)
    print("  SECURENET SOC — PRODUCTION ML TRAINING PIPELINE")
    print("=" * 65)

    # ------------------------------------------------------------------
    # 1. Load and prepare data
    # ------------------------------------------------------------------
    print("\n[1/6] Loading and preparing dataset...")
    X, y = prepare_training_data(csv_path)
    dataset_name = Path(csv_path).stem

    # ------------------------------------------------------------------
    # 2. Define model candidates
    # ------------------------------------------------------------------
    print("\n[2/6] Defining model candidates...")

    models = {
        "RandomForest": Pipeline(
            [
                ("scaler", StandardScaler()),
                (
                    "model",
                    RandomForestClassifier(
                        n_estimators=100,
                        max_depth=20,
                        min_samples_split=5,
                        min_samples_leaf=2,
                        random_state=42,
                        n_jobs=-1,
                        class_weight="balanced",
                    ),
                ),
            ]
        ),
    }
    print(f"  ✓ RandomForest (100 trees, max_depth=20, balanced)")

    # Calculate scale_pos_weight for class imbalance (shared by boosting models)
    neg_count = int((y == 0).sum())
    pos_count = int((y == 1).sum())
    scale_weight = neg_count / pos_count if pos_count > 0 else 1.0

    if HAS_XGBOOST:
        models["XGBoost"] = Pipeline(
            [
                ("scaler", StandardScaler()),
                (
                    "model",
                    XGBClassifier(
                        n_estimators=100,
                        max_depth=8,
                        learning_rate=0.1,
                        random_state=42,
                        n_jobs=-1,
                        eval_metric="logloss",
                        scale_pos_weight=scale_weight,
                        use_label_encoder=False,
                    ),
                ),
            ]
        )
        print(f"  ✓ XGBoost (100 trees, max_depth=8, scale_pos_weight={scale_weight:.2f})")

    # GradientBoosting (sklearn built-in, always available)
    models["GradientBoosting"] = Pipeline(
        [
            ("scaler", StandardScaler()),
            (
                "model",
                GradientBoostingClassifier(
                    n_estimators=100,
                    max_depth=5,
                    learning_rate=0.1,
                    random_state=42,
                ),
            ),
        ]
    )
    print(f"  ✓ GradientBoosting (100 trees, max_depth=5)")

    if HAS_LIGHTGBM:
        models["LightGBM"] = Pipeline(
            [
                ("scaler", StandardScaler()),
                (
                    "model",
                    LGBMClassifier(
                        n_estimators=100,
                        max_depth=7,
                        learning_rate=0.1,
                        random_state=42,
                        n_jobs=-1,
                        scale_pos_weight=scale_weight,
                        verbose=-1,
                    ),
                ),
            ]
        )
        print(f"  ✓ LightGBM (100 trees, max_depth=7)")

    if HAS_CATBOOST:
        models["CatBoost"] = Pipeline(
            [
                ("scaler", StandardScaler()),
                (
                    "model",
                    CatBoostClassifier(
                        n_estimators=100,
                        max_depth=6,
                        learning_rate=0.1,
                        random_state=42,
                        verbose=False,
                        auto_class_weights="Balanced",
                    ),
                ),
            ]
        )
        print(f"  ✓ CatBoost (100 trees, max_depth=6)")

    # ------------------------------------------------------------------
    # 3. Cross-validation comparison
    # ------------------------------------------------------------------
    print("\n[3/6] Running 5-fold stratified cross-validation...")

    cv = StratifiedKFold(n_splits=5, shuffle=True, random_state=42)
    scoring = {
        "accuracy": "accuracy",
        "precision": "precision",
        "recall": "recall",
        "f1": "f1",
        "roc_auc": "roc_auc",
    }
    results = {}

    for name, pipeline in models.items():
        print(f"\n  Training: {name}...")
        start_time = time.time()

        cv_results = cross_validate(pipeline, X, y, cv=cv, scoring=scoring, n_jobs=-1)
        training_time = time.time() - start_time

        # Process results
        fold_scores = {
            metric: [cv_results[f"test_{metric}"][i] for i in range(5)] for metric in scoring.keys()
        }

        results[name] = {
            "accuracy": {
                "mean": float(cv_results["test_accuracy"].mean()),
                "std": float(cv_results["test_accuracy"].std()),
                "folds": fold_scores["accuracy"],
            },
            "precision": {
                "mean": float(cv_results["test_precision"].mean()),
                "std": float(cv_results["test_precision"].std()),
                "folds": fold_scores["precision"],
            },
            "recall": {
                "mean": float(cv_results["test_recall"].mean()),
                "std": float(cv_results["test_recall"].std()),
                "folds": fold_scores["recall"],
            },
            "f1": {
                "mean": float(cv_results["test_f1"].mean()),
                "std": float(cv_results["test_f1"].std()),
                "folds": fold_scores["f1"],
            },
            "roc_auc": {
                "mean": float(cv_results["test_roc_auc"].mean()),
                "std": float(cv_results["test_roc_auc"].std()),
                "folds": fold_scores["roc_auc"],
            },
            "training_time": training_time,
        }

        print(
            f"    Accuracy:  {cv_results['test_accuracy'].mean():.4f} ± {cv_results['test_accuracy'].std():.4f}"
        )
        print(
            f"    Precision: {cv_results['test_precision'].mean():.4f} ± {cv_results['test_precision'].std():.4f}"
        )
        print(
            f"    Recall:    {cv_results['test_recall'].mean():.4f} ± {cv_results['test_recall'].std():.4f}"
        )
        print(
            f"    F1:        {cv_results['test_f1'].mean():.4f} ± {cv_results['test_f1'].std():.4f}"
        )
        print(
            f"    ROC AUC:   {cv_results['test_roc_auc'].mean():.4f} ± {cv_results['test_roc_auc'].std():.4f}"
        )
        print(f"    Time:      {training_time:.1f}s")

    # ------------------------------------------------------------------
    # 4. Select best model and train on full data
    # ------------------------------------------------------------------
    print("\n[4/6] Selecting best model by F1 score...")

    best_name = max(results, key=lambda k: results[k]["f1"]["mean"])
    best_pipeline = models[best_name]

    best_f1 = results[best_name]["f1"]["mean"]
    print(f"  ★ Winner: {best_name} (F1 = {best_f1:.4f})")

    print(f"\n  Training {best_name} on full dataset ({len(X)} samples)...")
    start_train = time.time()
    best_pipeline.fit(X, y)
    full_training_time = time.time() - start_train

    # Full evaluation with all metrics
    y_pred = best_pipeline.predict(X)
    y_proba = (
        best_pipeline.predict_proba(X)[:, 1] if hasattr(best_pipeline, "predict_proba") else None
    )

    full_accuracy = accuracy_score(y, y_pred)
    full_precision = precision_score(y, y_pred, zero_division=0)
    full_recall = recall_score(y, y_pred, zero_division=0)
    full_f1 = f1_score(y, y_pred, zero_division=0)
    full_roc = roc_auc_score(y, y_proba) if y_proba is not None else None

    cm = confusion_matrix(y, y_pred)
    confusion_matrix_data = {
        "tn": int(cm[0, 0]),
        "fp": int(cm[0, 1]),
        "fn": int(cm[1, 0]),
        "tp": int(cm[1, 1]),
    }

    print(f"\n  Classification Report (full training set):")
    print(classification_report(y, y_pred, target_names=["Benign", "Attack"], digits=4))
    print(f"  Confusion Matrix: TN={cm[0, 0]} FP={cm[0, 1]} FN={cm[1, 0]} TP={cm[1, 1]}")

    # Feature importance if available
    feature_importance_data = {}
    if hasattr(best_pipeline.named_steps["model"], "feature_importances_"):
        importances = best_pipeline.named_steps["model"].feature_importances_
        feature_importance_data = {
            col: float(imp) for col, imp in zip(FEATURE_COLUMNS, importances)
        }
        print(f"\n  Top 5 Features by Importance:")
        sorted_imp = sorted(feature_importance_data.items(), key=lambda x: x[1], reverse=True)
        for feat, imp in sorted_imp[:5]:
            print(f"    {feat}: {imp:.4f}")

    # ------------------------------------------------------------------
    # 5. Save model + metadata
    # ------------------------------------------------------------------
    print("\n[5/6] Saving model artifacts...")

    model_version = datetime.now().strftime("%Y%m%d_%H%M%S")
    model_path = os.path.join(output_dir, "model.joblib")
    metadata_path = os.path.join(output_dir, "model_metadata.json")

    joblib.dump(best_pipeline, model_path)

    metadata = {
        "version": model_version,
        "algorithm": best_name,
        "features": FEATURE_COLUMNS,
        "n_features": len(FEATURE_COLUMNS),
        "n_training_samples": int(len(X)),
        "class_distribution": {
            "benign": int((y == 0).sum()),
            "attack": int((y == 1).sum()),
        },
        "full_training_metrics": {
            "accuracy": round(full_accuracy, 6),
            "precision": round(full_precision, 6),
            "recall": round(full_recall, 6),
            "f1": round(full_f1, 6),
            "roc_auc": round(full_roc, 6) if full_roc else None,
        },
        "cross_validation": results,
        "trained_at": datetime.now().isoformat(),
        "dataset": dataset_name,
        "pipeline_steps": [step[0] for step in best_pipeline.steps],
    }

    with open(metadata_path, "w") as f:
        json.dump(metadata, f, indent=2)

    # Compute and save feature baselines for drift detection
    try:
        baseline_path = os.path.join(output_dir, "feature_baselines.json")
        baselines = DriftDetector.compute_baselines(X, FEATURE_COLUMNS)
        with open(baseline_path, "w") as f:
            json.dump(baselines, f, indent=2)
        print(f"  Baselines saved to: {baseline_path}")
    except Exception as e:
        print(f"  [!] Failed to save baselines: {e}")

    print(f"\n  Model saved to:    {model_path}")
    print(f"  Metadata saved to: {metadata_path}")
    print(f"  Version:           {model_version}")
    print(f"  Pipeline:          {' → '.join(metadata['pipeline_steps'])}")

    # ------------------------------------------------------------------
    # 6. Log experiment to database (async)
    # ------------------------------------------------------------------
    print("\n[6/6] Logging experiment to database...")

    hyperparameters = {
        best_name: {
            param: str(value)
            for param, value in best_pipeline.named_steps["model"].get_params().items()
            if not param.startswith("_")
        }
    }

    experiment_id = None
    promoted = False
    try:
        experiment_id, promoted = asyncio.run(
            log_experiment_to_db(
                experiment_name=f"{best_name}_{model_version}",
                algorithm=best_name,
                hyperparameters=hyperparameters,
                dataset_name=dataset_name,
                dataset_rows=int(len(X)),
                feature_count=len(FEATURE_COLUMNS),
                accuracy=full_accuracy,
                precision=full_precision,
                recall=full_recall,
                f1=full_f1,
                roc_auc=full_roc if full_roc else 0.0,
                cv_scores=results[best_name],
                cv_mean=results[best_name]["f1"]["mean"],
                cv_std=results[best_name]["f1"]["std"],
                confusion_matrix_data=confusion_matrix_data,
                feature_importance_data=feature_importance_data,
                model_file_path=model_path,
                training_time_seconds=full_training_time,
                notes=f"Auto-trained on {dataset_name} with {len(X)} samples",
            )
        )
    except Exception as e:
        print(f"  [!] Database logging skipped: {e}")

    # ------------------------------------------------------------------
    # Comparison table
    # ------------------------------------------------------------------
    print("\n" + "=" * 65)
    print("  MODEL COMPARISON TABLE")
    print("=" * 65)
    header = f"  {'Algorithm':<20} | {'F1':>6} | {'Accuracy':>8} | {'Time':>7} | Winner?"
    print(header)
    print("  " + "-" * len(header.strip()))
    for name in sorted(results, key=lambda k: results[k]["f1"]["mean"], reverse=True):
        r = results[name]
        winner = " ★" if name == best_name else ""
        print(
            f"  {name:<20} | {r['f1']['mean']:.4f} | {r['accuracy']['mean']:.6f} | {r['training_time']:>6.1f}s |{winner}"
        )
    print("=" * 65)

    print("\n" + "=" * 65)
    print("  TRAINING COMPLETE — Model ready for deployment")
    if promoted:
        print("  ✓ Best model automatically promoted to model_registry")
    else:
        print("  ℹ Model saved but not promoted (existing model is better)")
    print("=" * 65)

    return best_pipeline, metadata, experiment_id, promoted


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    default_csv = os.path.join(
        os.path.dirname(os.path.dirname(__file__)),
        "Friday-WorkingHours-Afternoon-DDos.pcap_ISCX.csv",
    )

    csv_path = sys.argv[1] if len(sys.argv) > 1 else default_csv

    if not os.path.exists(csv_path):
        print(f"[!] Dataset not found: {csv_path}")
        print(f"    Download CICIDS2017 from: https://www.unb.ca/cic/datasets/ids-2017.html")
        print(f"    Place the CSV in the project root directory.")
        sys.exit(1)

    pipeline, metadata, exp_id, promoted = train_and_evaluate(csv_path)
    print(f"\n✓ Training complete. Experiment ID: {exp_id}")
    if promoted:
        print(f"✓ Model automatically activated for serving")
