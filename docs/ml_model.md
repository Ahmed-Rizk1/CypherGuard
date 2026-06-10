# SecureNet SOC — ML Model Documentation

## Overview

The ML Engine uses a supervised Random Forest classifier trained on the CICIDS2017 dataset to detect network intrusions in real-time.

## Model Architecture

| Property | Value |
|---|---|
| **Algorithm** | Random Forest (scikit-learn) |
| **Task** | Binary classification (benign vs malicious) |
| **Features** | 11 network flow statistics |
| **Training Data** | CICIDS2017 (Canadian Institute for Cybersecurity) |
| **Output** | `0` (benign) or `1` (malicious) + confidence score |
| **Serving** | joblib serialized model + Redis Streams consumer |

## Feature Set

These 11 features are computed by the Extractor service from raw packet data:

| # | Feature (CICIDS Name) | Extractor Name | Description |
|---|---|---|---|
| 1 | Flow Bytes/s | `bytes_per_sec` | Throughput in bytes/second |
| 2 | Flow Packets/s | `packets_per_sec` | Packet rate |
| 3 | Avg Packet Size | `avg_packet_size` | Mean packet size in bytes |
| 4 | Flow Duration | `flow_duration` | Total flow duration (seconds) |
| 5 | Total Fwd Packets | `packet_count` | Forward packet count |
| 6 | Total Length of Fwd Packets | `total_bytes` | Total forward bytes |
| 7 | Fwd Packet Length Mean | `fwd_pkt_len_mean` | Mean forward packet size |
| 8 | Fwd Packet Length Std | `fwd_pkt_len_std` | Std dev of forward packet size |
| 9 | Flow IAT Mean | `flow_iat_mean` | Mean inter-arrival time |
| 10 | Flow IAT Std | `flow_iat_std` | Std dev of inter-arrival time |
| 11 | Small Packet Ratio | `small_packet_ratio` | Ratio of packets < 100 bytes |

**Important:** Changes to features require retraining. Feature schema is enforced in `ml_engine/feature_engineering.py`.

## Training Pipeline

```bash
python ml_engine/train_production.py <path_to_cicids2017.csv>
```

### Output Files

| File | Purpose |
|---|---|
| `ml_engine/models/model.joblib` | Serialized model |
| `ml_engine/models/model_metadata.json` | Version, accuracy, feature list |
| `ml_engine/models/feature_baselines.json` | Distribution baselines for drift detection |

### Training Process

1. Load CICIDS2017 CSV (column name cleaning, inf/NaN removal)
2. Extract 11 features from available columns (missing → fill with 0)
3. Binary label encoding: BENIGN=0, Attack=1
4. Train/test split (80/20, stratified)
5. Fit Random Forest with optimized hyperparameters
6. Evaluate: accuracy, F1 score, confusion matrix
7. Save model + metadata + feature baselines
8. Register in `model_registry` PostgreSQL table

## Inference Pipeline

```
Redis stream:features → ML Engine consumer → scikit-learn predict
                                           → predict_proba (confidence)
                                           → log to PostgreSQL
                                           → feed drift detector
                                           → publish to stream:alerts (if malicious)
```

### Performance

| Metric | Target | Typical |
|---|---|---|
| Inference latency (p50) | < 5ms | ~2ms |
| Inference latency (p95) | < 20ms | ~8ms |
| Throughput | > 5000/sec | ~10,000/sec |

## Feature Drift Detection

The drift detector compares runtime feature distributions against training baselines using KL divergence.

### Configuration

| Parameter | Default | Description |
|---|---|---|
| `DRIFT_BASELINE_PATH` | `ml_engine/models/feature_baselines.json` | Path to baselines |
| Window size | 1000 | Samples before checking |
| KL threshold | 0.5 | Divergence threshold |

### How It Works

1. Training pipeline computes histograms for each feature → `feature_baselines.json`
2. At runtime, every prediction's features are buffered
3. Every 1000 samples, KL divergence is computed against baselines
4. If KL > 0.5 for any feature:
   - Prometheus counter `securenet_feature_drift_detected_total` incremented
   - Warning logged with feature name and KL value
   - Grafana alert fires (`FeatureDriftDetected`)

### Remediation

When drift is detected:
1. Check if traffic patterns have legitimately changed
2. If model accuracy degraded, retrain with recent data
3. Use `POST /model/reload` to hot-reload without service restart

## Model Hot-Reload

```http
# Check model info
GET http://localhost:8002/model/info

# Reload model from disk (if file hash changed)
POST http://localhost:8002/model/reload
```

The ML Engine computes SHA256 hash of the model file at startup. On reload, it only loads if the hash has changed.

## LLM Classification (Post-ML)

After ML flags traffic as malicious, the LLM Analyzer provides:
- **Attack type** (DDoS, Port Scan, Brute Force, etc.)
- **Severity** (low, medium, high, critical)
- **Explanation** (2 sentences)
- **Recommendation** (1 sentence)

### Fallback Chain
1. **Cache** — Redis-cached LLM responses (bucketed by traffic profile)
2. **LLM** — GPT-4o-mini via OpenRouter (with circuit breaker)
3. **Heuristic** — Rule-based classification (free, instant)

### Prompt Versioning

Prompts are versioned in `shared/llm_config.py`:
- `v1` — Basic IDS analyst prompt
- `v2` — Senior SOC analyst with structured rules

LLM responses are validated with Pydantic schema before use. Invalid responses fall back to heuristics.
