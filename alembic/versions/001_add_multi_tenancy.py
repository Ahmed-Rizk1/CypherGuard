"""
Alembic Migration: Add multi-tenancy support.

Creates:
- tenants, sensors, api_keys, subscriptions, usage_records, notifications, invitations tables
- tenant_id column on all existing tables
- Default tenant for backward compatibility
- RLS policies for tenant isolation
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID, JSONB

# revision identifiers
revision = '001_add_multi_tenancy'
down_revision = None
branch_labels = None
depends_on = None

DEFAULT_TENANT_ID = '00000000-0000-0000-0000-000000000001'


def upgrade():
    # ---------------------------------------------------------------
    # 1. Create new tables
    # ---------------------------------------------------------------

    # Tenants table
    op.create_table(
        'tenants',
        sa.Column('id', UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text('gen_random_uuid()')),
        sa.Column('name', sa.String(255), nullable=False),
        sa.Column('slug', sa.String(100), unique=True, nullable=False),
        sa.Column('owner_id', UUID(as_uuid=True), nullable=True),
        sa.Column('plan', sa.String(50), server_default='free'),
        sa.Column('status', sa.String(20), server_default='trial'),
        sa.Column('trial_ends_at', sa.DateTime, nullable=True),
        sa.Column('stripe_customer_id', sa.String(255), nullable=True),
        sa.Column('stripe_subscription_id', sa.String(255), nullable=True),
        sa.Column('max_sensors', sa.Integer, server_default='1'),
        sa.Column('max_users', sa.Integer, server_default='1'),
        sa.Column('max_ai_analyses_monthly', sa.Integer, server_default='50'),
        sa.Column('ai_analyses_used', sa.Integer, server_default='0'),
        sa.Column('ai_analyses_reset_at', sa.DateTime, nullable=True),
        sa.Column('settings', JSONB, server_default='{}'),
        sa.Column('parent_tenant_id', UUID(as_uuid=True), nullable=True),
        sa.Column('mssp_mode', sa.Boolean, server_default='false'),
        sa.Column('created_at', sa.DateTime, server_default=sa.text('NOW()')),
        sa.Column('updated_at', sa.DateTime, nullable=True),
    )
    op.create_index('ix_tenants_slug', 'tenants', ['slug'])
    op.create_foreign_key('fk_tenants_parent', 'tenants', 'tenants',
                          ['parent_tenant_id'], ['id'])

    # Sensors table
    op.create_table(
        'sensors',
        sa.Column('id', UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text('gen_random_uuid()')),
        sa.Column('tenant_id', UUID(as_uuid=True),
                  sa.ForeignKey('tenants.id'), nullable=False),
        sa.Column('name', sa.String(255), nullable=False),
        sa.Column('api_key_hash', sa.String(255), nullable=False),
        sa.Column('api_key_prefix', sa.String(12), nullable=False),
        sa.Column('status', sa.String(20), server_default='pending'),
        sa.Column('last_heartbeat', sa.DateTime, nullable=True),
        sa.Column('last_ip', sa.String(45), nullable=True),
        sa.Column('config', JSONB, server_default='{}'),
        sa.Column('version', sa.String(50), nullable=True),
        sa.Column('created_at', sa.DateTime, server_default=sa.text('NOW()')),
    )
    op.create_index('ix_sensors_tenant_id', 'sensors', ['tenant_id'])

    # API Keys table
    op.create_table(
        'api_keys',
        sa.Column('id', UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text('gen_random_uuid()')),
        sa.Column('tenant_id', UUID(as_uuid=True),
                  sa.ForeignKey('tenants.id'), nullable=False),
        sa.Column('created_by', UUID(as_uuid=True),
                  sa.ForeignKey('users.id'), nullable=False),
        sa.Column('name', sa.String(255), nullable=False),
        sa.Column('key_hash', sa.String(255), nullable=False),
        sa.Column('key_prefix', sa.String(12), nullable=False),
        sa.Column('scopes', JSONB, server_default='{"read": true, "write": false}'),
        sa.Column('is_active', sa.Boolean, server_default='true'),
        sa.Column('last_used_at', sa.DateTime, nullable=True),
        sa.Column('expires_at', sa.DateTime, nullable=True),
        sa.Column('created_at', sa.DateTime, server_default=sa.text('NOW()')),
    )
    op.create_index('ix_api_keys_tenant_id', 'api_keys', ['tenant_id'])

    # Subscriptions table
    op.create_table(
        'subscriptions',
        sa.Column('id', UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text('gen_random_uuid()')),
        sa.Column('tenant_id', UUID(as_uuid=True),
                  sa.ForeignKey('tenants.id'), unique=True, nullable=False),
        sa.Column('stripe_subscription_id', sa.String(255), unique=True, nullable=False),
        sa.Column('stripe_customer_id', sa.String(255), nullable=False),
        sa.Column('plan', sa.String(50), nullable=False),
        sa.Column('status', sa.String(30), nullable=False),
        sa.Column('current_period_start', sa.DateTime, nullable=False),
        sa.Column('current_period_end', sa.DateTime, nullable=False),
        sa.Column('cancel_at_period_end', sa.Boolean, server_default='false'),
        sa.Column('created_at', sa.DateTime, server_default=sa.text('NOW()')),
        sa.Column('updated_at', sa.DateTime, nullable=True),
    )

    # Usage Records table
    op.create_table(
        'usage_records',
        sa.Column('id', UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text('gen_random_uuid()')),
        sa.Column('tenant_id', UUID(as_uuid=True),
                  sa.ForeignKey('tenants.id'), nullable=False),
        sa.Column('usage_type', sa.String(50), nullable=False),
        sa.Column('quantity', sa.Integer, nullable=False),
        sa.Column('period_start', sa.DateTime, nullable=False),
        sa.Column('period_end', sa.DateTime, nullable=False),
        sa.Column('reported_to_stripe', sa.Boolean, server_default='false'),
        sa.Column('created_at', sa.DateTime, server_default=sa.text('NOW()')),
    )
    op.create_index('ix_usage_records_tenant_id', 'usage_records', ['tenant_id'])

    # Notifications table
    op.create_table(
        'notifications',
        sa.Column('id', UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text('gen_random_uuid()')),
        sa.Column('tenant_id', UUID(as_uuid=True),
                  sa.ForeignKey('tenants.id'), nullable=False),
        sa.Column('user_id', UUID(as_uuid=True),
                  sa.ForeignKey('users.id'), nullable=True),
        sa.Column('type', sa.String(50), nullable=False),
        sa.Column('title', sa.String(255), nullable=False),
        sa.Column('message', sa.Text, nullable=False),
        sa.Column('data', JSONB, server_default='{}'),
        sa.Column('read_at', sa.DateTime, nullable=True),
        sa.Column('created_at', sa.DateTime, server_default=sa.text('NOW()')),
    )
    op.create_index('ix_notifications_tenant_id', 'notifications', ['tenant_id'])

    # Invitations table
    op.create_table(
        'invitations',
        sa.Column('id', UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text('gen_random_uuid()')),
        sa.Column('tenant_id', UUID(as_uuid=True),
                  sa.ForeignKey('tenants.id'), nullable=False),
        sa.Column('email', sa.String(255), nullable=False),
        sa.Column('role', sa.String(20), nullable=False, server_default='analyst'),
        sa.Column('invited_by', UUID(as_uuid=True),
                  sa.ForeignKey('users.id'), nullable=False),
        sa.Column('token', sa.String(255), unique=True, nullable=False),
        sa.Column('accepted_at', sa.DateTime, nullable=True),
        sa.Column('expires_at', sa.DateTime, nullable=False),
        sa.Column('created_at', sa.DateTime, server_default=sa.text('NOW()')),
    )
    op.create_index('ix_invitations_tenant_id', 'invitations', ['tenant_id'])

    # ---------------------------------------------------------------
    # 2. Add tenant_id to existing tables
    # ---------------------------------------------------------------
    for table in ['users', 'alerts', 'blocked_ips', 'decision_logs',
                  'ml_predictions', 'audit_log', 'model_registry']:
        op.add_column(table, sa.Column(
            'tenant_id', UUID(as_uuid=True), nullable=True
        ))

    # Add new user columns
    op.add_column('users', sa.Column('full_name', sa.String(255), nullable=True))
    op.add_column('users', sa.Column('is_email_verified', sa.Boolean,
                                      server_default='false'))

    # ---------------------------------------------------------------
    # 3. Create default tenant for existing data
    # ---------------------------------------------------------------
    op.execute(f"""
        INSERT INTO tenants (id, name, slug, plan, status, max_sensors, max_users, max_ai_analyses_monthly)
        VALUES ('{DEFAULT_TENANT_ID}', 'Default', 'default', 'enterprise', 'active', 100, 100, -1)
        ON CONFLICT (id) DO NOTHING
    """)

    # ---------------------------------------------------------------
    # 4. Backfill existing data with default tenant
    # ---------------------------------------------------------------
    for table in ['users', 'alerts', 'blocked_ips', 'decision_logs',
                  'ml_predictions', 'audit_log', 'model_registry']:
        op.execute(f"""
            UPDATE {table}
            SET tenant_id = '{DEFAULT_TENANT_ID}'
            WHERE tenant_id IS NULL
        """)

    # ---------------------------------------------------------------
    # 5. Add indexes for tenant_id
    # ---------------------------------------------------------------
    for table in ['users', 'alerts', 'blocked_ips', 'decision_logs',
                  'ml_predictions', 'audit_log', 'model_registry']:
        op.create_index(f'ix_{table}_tenant_id', table, ['tenant_id'])

    # ---------------------------------------------------------------
    # 6. Add foreign key constraints
    # ---------------------------------------------------------------
    for table in ['users', 'alerts', 'blocked_ips', 'decision_logs',
                  'ml_predictions', 'audit_log', 'model_registry']:
        op.create_foreign_key(
            f'fk_{table}_tenant_id', table, 'tenants',
            ['tenant_id'], ['id']
        )

    # ---------------------------------------------------------------
    # 7. Add owner_id FK to tenants (now that users table has tenant_id)
    # ---------------------------------------------------------------
    op.create_foreign_key(
        'fk_tenants_owner', 'tenants', 'users',
        ['owner_id'], ['id']
    )

    # ---------------------------------------------------------------
    # 8. Enable Row-Level Security
    # ---------------------------------------------------------------
    for table in ['alerts', 'blocked_ips', 'decision_logs', 'ml_predictions', 'audit_log']:
        op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")
        op.execute(f"""
            CREATE POLICY tenant_isolation_{table} ON {table}
            USING (tenant_id = current_setting('app.tenant_id', true)::uuid)
        """)
        op.execute(f"""
            CREATE POLICY tenant_insert_{table} ON {table}
            FOR INSERT WITH CHECK (tenant_id = current_setting('app.tenant_id', true)::uuid)
        """)

    # Backfill verification of existing email
    op.execute(f"""
        UPDATE users SET is_email_verified = true WHERE tenant_id = '{DEFAULT_TENANT_ID}'
    """)


def downgrade():
    # Drop RLS policies
    for table in ['alerts', 'blocked_ips', 'decision_logs', 'ml_predictions', 'audit_log']:
        op.execute(f"DROP POLICY IF EXISTS tenant_isolation_{table} ON {table}")
        op.execute(f"DROP POLICY IF EXISTS tenant_insert_{table} ON {table}")
        op.execute(f"ALTER TABLE {table} DISABLE ROW LEVEL SECURITY")

    # Drop foreign keys and columns
    for table in ['users', 'alerts', 'blocked_ips', 'decision_logs',
                  'ml_predictions', 'audit_log', 'model_registry']:
        op.drop_constraint(f'fk_{table}_tenant_id', table, type_='foreignkey')
        op.drop_index(f'ix_{table}_tenant_id', table_name=table)
        op.drop_column(table, 'tenant_id')

    op.drop_column('users', 'full_name')
    op.drop_column('users', 'is_email_verified')

    # Drop new tables
    for table in ['invitations', 'notifications', 'usage_records',
                  'subscriptions', 'api_keys', 'sensors', 'tenants']:
        op.drop_table(table)
