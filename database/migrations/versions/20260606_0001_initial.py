"""Create the Sentinel Phase 1 schemas.

Revision ID: 20260606_0001
Revises:
Create Date: 2026-06-06
"""

from pathlib import Path

from alembic import op

revision = "20260606_0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    schema_path = Path(__file__).resolve().parents[2] / "schema.sql"
    sql = schema_path.read_text(encoding="utf-8")
    for statement in sql.split(";"):
        statement = statement.strip()
        if statement:
            op.execute(statement)


def downgrade() -> None:
    for schema in (
        "audit",
        "operations",
        "intelligence",
        "relationships",
        "inventory",
        "identity",
        "platform",
    ):
        op.execute(f'DROP SCHEMA IF EXISTS "{schema}" CASCADE')
