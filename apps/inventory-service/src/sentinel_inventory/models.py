from datetime import datetime
from uuid import UUID

from sqlalchemy import (
    JSON,
    BigInteger,
    DateTime,
    ForeignKey,
    Index,
    String,
    Text,
    UniqueConstraint,
    Uuid,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from sentinel_common.db import Base
from sentinel_common.models import TimestampMixin, UUIDPrimaryKeyMixin


class Subscription(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "subscriptions"
    __table_args__ = (
        UniqueConstraint("tenant_id", "azure_subscription_id", name="uq_subscription_azure"),
        Index("ix_subscriptions_tenant_state", "tenant_id", "state"),
        {"schema": "inventory"},
    )

    tenant_id: Mapped[UUID] = mapped_column(Uuid, nullable=False)
    azure_subscription_id: Mapped[UUID] = mapped_column(Uuid, nullable=False)
    display_name: Mapped[str] = mapped_column(String(255), nullable=False)
    state: Mapped[str] = mapped_column(String(32), nullable=False)
    management_group_id: Mapped[str | None] = mapped_column(Text)
    last_sync_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    version: Mapped[int] = mapped_column(nullable=False, default=1)


class ResourceGroup(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "resource_groups"
    __table_args__ = (
        UniqueConstraint(
            "tenant_id", "subscription_id", "normalized_name", name="uq_resource_group_scope"
        ),
        Index("ix_resource_groups_tenant_subscription", "tenant_id", "subscription_id"),
        {"schema": "inventory"},
    )

    tenant_id: Mapped[UUID] = mapped_column(Uuid, nullable=False)
    subscription_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("inventory.subscriptions.id"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    normalized_name: Mapped[str] = mapped_column(String(255), nullable=False)
    location: Mapped[str | None] = mapped_column(String(128))
    tags: Mapped[dict[str, str]] = mapped_column(JSON, nullable=False, default=dict)
    state: Mapped[str] = mapped_column(String(32), nullable=False, default="active")
    last_seen_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class Resource(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "resources"
    __table_args__ = (
        UniqueConstraint("tenant_id", "normalized_resource_id", name="uq_resource_arm_id"),
        UniqueConstraint("tenant_id", "id", name="uq_resource_tenant_id"),
        Index("ix_resources_tenant_type_state", "tenant_id", "resource_type", "state"),
        Index("ix_resources_tenant_group", "tenant_id", "resource_group"),
        {"schema": "inventory"},
    )

    tenant_id: Mapped[UUID] = mapped_column(Uuid, nullable=False)
    subscription_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("inventory.subscriptions.id"), nullable=False
    )
    azure_resource_id: Mapped[str] = mapped_column(Text, nullable=False)
    normalized_resource_id: Mapped[str] = mapped_column(Text, nullable=False)
    resource_type: Mapped[str] = mapped_column(String(255), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    resource_group: Mapped[str] = mapped_column(String(255), nullable=False)
    location: Mapped[str | None] = mapped_column(String(128))
    kind: Mapped[str | None] = mapped_column(String(128))
    sku: Mapped[str | None] = mapped_column(String(255))
    tags: Mapped[dict[str, str]] = mapped_column(JSON, nullable=False, default=dict)
    properties: Mapped[dict[str, object]] = mapped_column(JSON, nullable=False, default=dict)
    source_etag: Mapped[str | None] = mapped_column(String(255))
    provisioning_state: Mapped[str | None] = mapped_column(String(64))
    state: Mapped[str] = mapped_column(String(32), nullable=False, default="active")
    first_seen_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    last_seen_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    missing_since: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    version: Mapped[int] = mapped_column(nullable=False, default=1)


class SyncJob(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "sync_jobs"
    __table_args__ = (
        Index("ix_sync_jobs_tenant_requested", "tenant_id", "requested_at"),
        Index("ix_sync_jobs_status_heartbeat", "status", "heartbeat_at"),
        UniqueConstraint("tenant_id", "idempotency_key", name="uq_sync_job_idempotency"),
        {"schema": "inventory"},
    )

    tenant_id: Mapped[UUID] = mapped_column(Uuid, nullable=False)
    requested_by: Mapped[UUID] = mapped_column(Uuid, nullable=False)
    mode: Mapped[str] = mapped_column(String(32), nullable=False)
    scope: Mapped[dict[str, object]] = mapped_column(JSON, nullable=False)
    idempotency_key: Mapped[str] = mapped_column(String(255), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="queued")
    resources_seen: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    resources_changed: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    error_summary: Mapped[dict[str, object] | None] = mapped_column(JSON)
    correlation_id: Mapped[UUID] = mapped_column(Uuid, nullable=False)
    requested_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    heartbeat_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
