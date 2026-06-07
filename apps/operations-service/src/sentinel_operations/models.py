from datetime import datetime
from uuid import UUID

from sqlalchemy import JSON, DateTime, Index, String, Text, UniqueConstraint, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from sentinel_common.db import Base
from sentinel_common.models import TimestampMixin, UUIDPrimaryKeyMixin


class Operation(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "operations"
    __table_args__ = (
        UniqueConstraint("tenant_id", "idempotency_key", name="uq_operation_idempotency"),
        Index("ix_operations_tenant_status", "tenant_id", "status"),
        {"schema": "operations"},
    )

    tenant_id: Mapped[UUID] = mapped_column(Uuid, nullable=False)
    assessment_id: Mapped[UUID] = mapped_column(Uuid, nullable=False)
    assessment_input_sha256: Mapped[str] = mapped_column(String(71), nullable=False)
    action_type: Mapped[str] = mapped_column(String(255), nullable=False)
    target_resource_id: Mapped[UUID] = mapped_column(Uuid, nullable=False)
    requested_by: Mapped[UUID] = mapped_column(Uuid, nullable=False)
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="draft")
    idempotency_key: Mapped[str] = mapped_column(String(255), nullable=False)
    policy_snapshot: Mapped[dict[str, object]] = mapped_column(JSON, nullable=False)
    parameters_snapshot: Mapped[dict[str, object]] = mapped_column(JSON, nullable=False)
    scheduled_for: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    result_summary: Mapped[dict[str, object] | None] = mapped_column(JSON)
    failure_code: Mapped[str | None] = mapped_column(String(128))
    correlation_id: Mapped[UUID] = mapped_column(Uuid, nullable=False)
    version: Mapped[int] = mapped_column(nullable=False, default=1)
