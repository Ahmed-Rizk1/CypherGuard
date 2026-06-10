"""Phase 5: Add ML experiment tracking table for automated model comparison and promotion.

Revision ID: phase5ml001
Revises: 002_add_composite_indexes
Create Date: 2026-05-23

This migration adds the ml_experiments table which enables:
- Full history of all model training runs
- Automatic best-model detection
- Hyperparameter tracking
- Cross-validation metrics
- Feature importance logging
- Model promotion workflow (like MLflow)

MULTI-TENANT: Includes tenant_id column and RLS policy for tenant isolation.
Experiments from the training pipeline (system-level) use tenant_id = NULL.
Experiments created via API routes are scoped to the requesting tenant.
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID, JSONB


revision = "phase5ml001"
down_revision = "002_add_composite_indexes"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Create ml_experiments table with tenant_id for multi-tenant isolation
    op.create_table(
        "ml_experiments",
        sa.Column("id", UUID(as_uuid=True), nullable=False, primary_key=True),
        # MULTI-TENANT: tenant_id is nullable because system-level training
        # runs (auto-retrain, CLI) don't belong to any specific tenant.
        sa.Column("tenant_id", UUID(as_uuid=True), nullable=True),
        sa.Column("experiment_name", sa.String(255), nullable=False),
        sa.Column("algorithm", sa.String(100), nullable=False),
        sa.Column("hyperparameters", JSONB(), nullable=False),
        sa.Column("dataset_name", sa.String(255), nullable=True),
        sa.Column("dataset_rows", sa.Integer(), nullable=True),
        sa.Column("feature_count", sa.Integer(), nullable=True),
        # Training metrics
        sa.Column("accuracy", sa.Float(), nullable=True),
        sa.Column("precision", sa.Float(), nullable=True),
        sa.Column("recall", sa.Float(), nullable=True),
        sa.Column("f1_score", sa.Float(), nullable=True),
        sa.Column("roc_auc", sa.Float(), nullable=True),
        # Cross-validation
        sa.Column("cv_scores", JSONB(), nullable=True),
        sa.Column("cv_mean", sa.Float(), nullable=True),
        sa.Column("cv_std", sa.Float(), nullable=True),
        # Model artifacts
        sa.Column("confusion_matrix", JSONB(), nullable=True),
        sa.Column("feature_importance", JSONB(), nullable=True),
        sa.Column("model_file_path", sa.String(500), nullable=True),
        sa.Column("model_hash", sa.String(64), nullable=True),
        # Training metadata
        sa.Column("training_time_seconds", sa.Float(), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        # Activation tracking
        sa.Column("is_best", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("promoted_to_registry", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("registry_id", UUID(as_uuid=True), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        # Foreign keys
        sa.ForeignKeyConstraint(["registry_id"], ["model_registry.id"]),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
    )

    # Create indexes for efficient queries
    op.create_index("idx_ml_experiments_tenant", "ml_experiments", ["tenant_id"])
    op.create_index("idx_ml_experiments_created", "ml_experiments", [sa.text("created_at DESC")])
    op.create_index("idx_ml_experiments_best", "ml_experiments", ["is_best"])
    op.create_index("idx_ml_experiments_algorithm", "ml_experiments", ["algorithm"])
    op.create_index(
        "idx_ml_experiments_tenant_created",
        "ml_experiments",
        ["tenant_id", sa.text("created_at DESC")],
    )

    # RLS policy: tenants can only see their own experiments + system experiments (tenant_id IS NULL)
    op.execute("ALTER TABLE ml_experiments ENABLE ROW LEVEL SECURITY")
    op.execute("""
        CREATE POLICY tenant_isolation_policy ON ml_experiments
        FOR ALL
        USING (
            tenant_id::text = current_setting('app.tenant_id', true)
            OR tenant_id IS NULL
            OR current_setting('app.tenant_id', true) = ''
        )
    """)


def downgrade() -> None:
    op.execute("DROP POLICY IF EXISTS tenant_isolation_policy ON ml_experiments")
    op.execute("ALTER TABLE ml_experiments DISABLE ROW LEVEL SECURITY")
    op.drop_index("idx_ml_experiments_tenant_created", table_name="ml_experiments")
    op.drop_index("idx_ml_experiments_algorithm", table_name="ml_experiments")
    op.drop_index("idx_ml_experiments_best", table_name="ml_experiments")
    op.drop_index("idx_ml_experiments_created", table_name="ml_experiments")
    op.drop_index("idx_ml_experiments_tenant", table_name="ml_experiments")
    op.drop_table("ml_experiments")
