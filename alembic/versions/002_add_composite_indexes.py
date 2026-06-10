"""
Alembic Migration: Add composite indexes and unique email constraint.

Performance optimization for multi-tenant query patterns and security
constraint to prevent duplicate email registrations.

RATIONALE:
- Single-column tenant_id indexes are insufficient for queries that
  filter by tenant_id + time/status. Composite indexes reduce full
  table scans to index-only operations.
- A partial index on blocked_ips (is_active=true) dramatically improves
  firewall status queries since most records are historical.
- The unique email constraint prevents duplicate account creation and
  enables future SSO integration.
"""

from alembic import op
import sqlalchemy as sa

# revision identifiers
revision = '002_add_composite_indexes'
down_revision = '001_add_multi_tenancy'
branch_labels = None
depends_on = None


def upgrade():
    # -------------------------------------------------------------------
    # Composite indexes for high-frequency query patterns
    # -------------------------------------------------------------------

    # Alerts: tenant + time range (dashboard, cursor pagination)
    # Query pattern: WHERE tenant_id = ? ORDER BY created_at DESC
    op.create_index(
        'ix_alerts_tenant_created',
        'alerts',
        ['tenant_id', sa.text('created_at DESC')],
    )

    # Alerts: tenant + status (filtered alert views)
    # Query pattern: WHERE tenant_id = ? AND status = ?
    op.create_index(
        'ix_alerts_tenant_status',
        'alerts',
        ['tenant_id', 'status'],
    )

    # BlockedIPs: tenant + active (firewall status page)
    # Partial index — only indexes active blocks, which is the hot path
    op.execute("""
        CREATE INDEX ix_blocked_tenant_active
        ON blocked_ips (tenant_id, created_at DESC)
        WHERE is_active = true
    """)

    # Notifications: tenant + user + time (notification center)
    # Query pattern: WHERE tenant_id = ? AND (user_id = ? OR user_id IS NULL) ORDER BY created_at DESC
    op.create_index(
        'ix_notifications_tenant_user',
        'notifications',
        ['tenant_id', 'user_id', sa.text('created_at DESC')],
    )

    # Audit log: tenant + time range (audit trail queries)
    op.create_index(
        'ix_audit_tenant_created',
        'audit_log',
        ['tenant_id', sa.text('created_at DESC')],
    )

    # ML predictions: tenant + time range
    op.create_index(
        'ix_mlpred_tenant_created',
        'ml_predictions',
        ['tenant_id', sa.text('created_at DESC')],
    )

    # Sensors: tenant + status (sensor management page)
    op.create_index(
        'ix_sensors_tenant_status',
        'sensors',
        ['tenant_id', 'status'],
    )

    # Usage records: tenant + billing period
    op.create_index(
        'ix_usage_tenant_period',
        'usage_records',
        ['tenant_id', 'period_start', 'period_end'],
    )

    # -------------------------------------------------------------------
    # Unique email constraint (globally unique)
    # -------------------------------------------------------------------
    # Prevents duplicate registrations and enables future SSO.
    # Uses a unique index instead of a constraint for better error messages.
    op.create_index(
        'ix_users_email_unique',
        'users',
        ['email'],
        unique=True,
    )


def downgrade():
    # Drop all composite indexes
    op.drop_index('ix_users_email_unique', table_name='users')
    op.drop_index('ix_usage_tenant_period', table_name='usage_records')
    op.drop_index('ix_sensors_tenant_status', table_name='sensors')
    op.drop_index('ix_mlpred_tenant_created', table_name='ml_predictions')
    op.drop_index('ix_audit_tenant_created', table_name='audit_log')
    op.drop_index('ix_notifications_tenant_user', table_name='notifications')
    op.drop_index('ix_blocked_tenant_active', table_name='blocked_ips')
    op.drop_index('ix_alerts_tenant_status', table_name='alerts')
    op.drop_index('ix_alerts_tenant_created', table_name='alerts')
