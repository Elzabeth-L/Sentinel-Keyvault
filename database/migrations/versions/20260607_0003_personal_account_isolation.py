"""isolate personal Microsoft accounts and retain OAuth authority

Revision ID: 20260607_0003
Revises: 20260607_0002
Create Date: 2026-06-07
"""

from collections.abc import Sequence

from alembic import op

revision: str = "20260607_0003"
down_revision: str | None = "20260607_0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        """
        ALTER TABLE identity.tenants
            ADD COLUMN IF NOT EXISTS identity_scope_key text,
            ADD COLUMN IF NOT EXISTS account_type text NOT NULL DEFAULT 'organization';

        UPDATE identity.tenants
        SET identity_scope_key = 'tenant:' || entra_tenant_id::text
        WHERE identity_scope_key IS NULL;

        ALTER TABLE identity.tenants
            ALTER COLUMN identity_scope_key SET NOT NULL;

        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1
                FROM pg_constraint
                WHERE conname = 'ux_tenants_identity_scope_key'
                  AND conrelid = 'identity.tenants'::regclass
            ) THEN
                ALTER TABLE identity.tenants
                    ADD CONSTRAINT ux_tenants_identity_scope_key
                    UNIQUE (identity_scope_key);
            END IF;
            IF NOT EXISTS (
                SELECT 1
                FROM pg_constraint
                WHERE conname = 'tenants_account_type'
                  AND conrelid = 'identity.tenants'::regclass
            ) THEN
                ALTER TABLE identity.tenants
                    ADD CONSTRAINT tenants_account_type
                    CHECK (account_type IN ('organization', 'personal'));
            END IF;
        END
        $$;

        ALTER TABLE identity.tenants
            DROP CONSTRAINT IF EXISTS tenants_entra_tenant_id_key;

        CREATE INDEX IF NOT EXISTS ix_tenants_entra_tenant_id
            ON identity.tenants (entra_tenant_id);

        ALTER TABLE identity.oauth_connections
            ADD COLUMN IF NOT EXISTS token_authority text;

        UPDATE identity.oauth_connections AS connection
        SET token_authority = tenant.entra_tenant_id::text
        FROM identity.tenants AS tenant
        WHERE tenant.id = connection.tenant_id;

        ALTER TABLE identity.oauth_connections
            ALTER COLUMN token_authority SET NOT NULL;
        """
    )


def downgrade() -> None:
    op.execute(
        """
        ALTER TABLE identity.oauth_connections
            DROP COLUMN token_authority;

        DROP INDEX IF EXISTS identity.ix_tenants_entra_tenant_id;

        ALTER TABLE identity.tenants
            DROP CONSTRAINT tenants_account_type,
            DROP CONSTRAINT ux_tenants_identity_scope_key,
            DROP COLUMN account_type,
            DROP COLUMN identity_scope_key,
            ADD CONSTRAINT tenants_entra_tenant_id_key UNIQUE (entra_tenant_id);
        """
    )
