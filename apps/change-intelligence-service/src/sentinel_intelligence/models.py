from datetime import datetime
from uuid import UUID

from sqlalchemy import JSON, DateTime, Index, SmallInteger, String, Text, UniqueConstraint, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from sentinel_common.db import Base
from sentinel_common.models import TimestampMixin, UUIDPrimaryKeyMixin


class ChangeAssessment(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "change_assessments"
    __table_args__ = (
        UniqueConstraint("tenant_id", "id", name="uq_assessment_tenant_id"),
        Index("ix_assessments_tenant_created", "tenant_id", "created_at"),
        Index("ix_assessments_tenant_target", "tenant_id", "target_resource_id"),
        {"schema": "intelligence"},
    )

    tenant_id: Mapped[UUID] = mapped_column(Uuid, nullable=False)
    requested_by: Mapped[UUID] = mapped_column(Uuid, nullable=False)
    target_resource_id: Mapped[UUID] = mapped_column(Uuid, nullable=False)
    action_type: Mapped[str] = mapped_column(String(255), nullable=False)
    parameters: Mapped[dict[str, object]] = mapped_column(JSON, nullable=False, default=dict)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="draft")
    risk_score: Mapped[int | None] = mapped_column(SmallInteger)
    risk_level: Mapped[str | None] = mapped_column(String(16))
    approval_required: Mapped[bool | None]
    rule_set_version: Mapped[str | None] = mapped_column(String(64))
    inventory_snapshot_id: Mapped[UUID | None] = mapped_column(Uuid)
    graph_snapshot_id: Mapped[UUID | None] = mapped_column(Uuid)
    target_etag: Mapped[str | None] = mapped_column(String(255))
    canonical_input: Mapped[dict[str, object]] = mapped_column(JSON, nullable=False)
    input_sha256: Mapped[str] = mapped_column(String(71), nullable=False)
    assessed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    failure_code: Mapped[str | None] = mapped_column(String(128))
    correlation_id: Mapped[UUID] = mapped_column(Uuid, nullable=False)
    version: Mapped[int] = mapped_column(nullable=False, default=1)


class AssessmentFinding(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "assessment_findings"
    __table_args__ = {"schema": "intelligence"}

    tenant_id: Mapped[UUID] = mapped_column(Uuid, nullable=False)
    assessment_id: Mapped[UUID] = mapped_column(Uuid, nullable=False)
    rule_id: Mapped[str] = mapped_column(String(128), nullable=False)
    severity: Mapped[str] = mapped_column(String(16), nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    evidence: Mapped[dict[str, object]] = mapped_column(JSON, nullable=False)
    remediation: Mapped[str | None] = mapped_column(Text)
