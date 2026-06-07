"""Add backend-owned Microsoft OAuth connections.

Revision ID: 20260607_0002
Revises: 20260606_0001
Create Date: 2026-06-07
"""

from alembic import op

revision = "20260607_0002"
down_revision = "20260606_0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS identity.oauth_connections (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id uuid NOT NULL REFERENCES identity.tenants(id) ON DELETE CASCADE,
            user_id uuid NOT NULL REFERENCES identity.users(id) ON DELETE CASCADE,
            provider text NOT NULL DEFAULT 'microsoft',
            scopes text NOT NULL,
            encrypted_refresh_token text NOT NULL,
            last_refreshed_at timestamptz,
            created_at timestamptz NOT NULL DEFAULT now(),
            updated_at timestamptz NOT NULL DEFAULT now(),
            UNIQUE (tenant_id, user_id, provider)
        )
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS ix_oauth_connections_tenant_user
        ON identity.oauth_connections (tenant_id, user_id)
        """
    )


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS identity.oauth_connections")
