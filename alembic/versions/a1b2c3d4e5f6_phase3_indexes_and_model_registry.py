"""Phase 3 migration: Add composite indexes, FK constraint fix, and model tracking table.

Revision ID: a1b2c3d4e5f6
Revises: 2e7b90c40679
Create Date: 2026-05-16
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID, JSONB

# revision identifiers
revision = 'a1b2c3d4e5f6'
down_revision = '2e7b90c40679'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 1. Composite index for efficient cursor pagination on alerts
    op.create_index(
        'idx_alerts_pagination',
        'alerts',
        [sa.text('created_at DESC'), sa.text('id DESC')],
    )

    # 2. Index for blocked IPs by creation date
    op.create_index(
        'idx_blocked_ips_created',
        'blocked_ips',
        [sa.text('created_at DESC')],
    )

    # 3. Index for ml_predictions by creation date
    op.create_index(
        'idx_ml_predictions_created',
        'ml_predictions',
        [sa.text('created_at DESC')],
    )

    # 4. Index for audit_log by creation date
    op.create_index(
        'idx_audit_log_created',
        'audit_log',
        [sa.text('created_at DESC')],
    )

    # 5. Index for decision_logs alert_id lookup
    op.create_index(
        'idx_decision_logs_alert_id',
        'decision_logs',
        ['alert_id'],
        unique=True,
    )

    # 6. Add model_registry table for tracking deployed models
    op.create_table(
        'model_registry',
        sa.Column('id', UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text('gen_random_uuid()')),
        sa.Column('version', sa.String(50), nullable=False, unique=True),
        sa.Column('algorithm', sa.String(100)),
        sa.Column('accuracy', sa.Float),
        sa.Column('f1_score', sa.Float),
        sa.Column('feature_columns', JSONB),
        sa.Column('training_samples', sa.Integer),
        sa.Column('file_hash', sa.String(64)),
        sa.Column('is_active', sa.Boolean, default=False),
        sa.Column('created_at', sa.DateTime, server_default=sa.text('NOW()')),
        sa.Column('activated_at', sa.DateTime, nullable=True),
    )

    # 7. Add user_id column to decision_logs for audit trail
    op.add_column('decision_logs',
        sa.Column('user_id', sa.String(255), nullable=True)
    )

    # 8. Add severity index on alerts for filtered queries
    op.create_index(
        'idx_alerts_severity',
        'alerts',
        ['severity'],
    )


def downgrade() -> None:
    op.drop_index('idx_alerts_pagination', table_name='alerts')
    op.drop_index('idx_blocked_ips_created', table_name='blocked_ips')
    op.drop_index('idx_ml_predictions_created', table_name='ml_predictions')
    op.drop_index('idx_audit_log_created', table_name='audit_log')
    op.drop_index('idx_decision_logs_alert_id', table_name='decision_logs')
    op.drop_index('idx_alerts_severity', table_name='alerts')
    op.drop_table('model_registry')
    op.drop_column('decision_logs', 'user_id')
