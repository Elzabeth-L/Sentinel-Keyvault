from datetime import datetime
from decimal import Decimal
from uuid import UUID

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    Index,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    Uuid,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from sentinel_common.db import Base
from sentinel_common.models import TimestampMixin, UUIDPrimaryKeyMixin


class ResourceNode(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "resource_nodes"
    __table_args__ = (
        UniqueConstraint("tenant_id", "inventory_resource_id", name="uq_node_inventory_id"),
        UniqueConstraint("tenant_id", "normalized_resource_id", name="uq_node_arm_id"),
        Index("ix_nodes_tenant_type", "tenant_id", "resource_type"),
        {"schema": "relationships"},
    )

    tenant_id: Mapped[UUID] = mapped_column(Uuid, nullable=False)
    inventory_resource_id: Mapped[UUID] = mapped_column(Uuid, nullable=False)
    azure_resource_id: Mapped[str] = mapped_column(Text, nullable=False)
    normalized_resource_id: Mapped[str] = mapped_column(Text, nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    resource_type: Mapped[str] = mapped_column(String(255), nullable=False)
    resource_group: Mapped[str] = mapped_column(String(255), nullable=False)
    properties: Mapped[dict[str, object]] = mapped_column(JSON, nullable=False, default=dict)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)


class Relationship(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "relationships"
    __table_args__ = (
        UniqueConstraint(
            "tenant_id",
            "source_resource_id",
            "target_resource_id",
            "relationship_type",
            "source_system",
            name="uq_relationship_edge",
        ),
        Index("ix_relationships_tenant_source", "tenant_id", "source_resource_id", "is_active"),
        Index("ix_relationships_tenant_target", "tenant_id", "target_resource_id", "is_active"),
        {"schema": "relationships"},
    )

    tenant_id: Mapped[UUID] = mapped_column(Uuid, nullable=False)
    source_resource_id: Mapped[UUID] = mapped_column(Uuid, nullable=False)
    target_resource_id: Mapped[UUID] = mapped_column(Uuid, nullable=False)
    relationship_type: Mapped[str] = mapped_column(String(128), nullable=False)
    source_system: Mapped[str] = mapped_column(String(64), nullable=False)
    dependency_strength: Mapped[str] = mapped_column(String(32), nullable=False)
    confidence: Mapped[Decimal] = mapped_column(Numeric(4, 3), nullable=False)
    evidence: Mapped[dict[str, object]] = mapped_column(JSON, nullable=False, default=dict)
    extractor_name: Mapped[str] = mapped_column(String(128), nullable=False)
    extractor_version: Mapped[str] = mapped_column(String(32), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    first_observed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    last_observed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
