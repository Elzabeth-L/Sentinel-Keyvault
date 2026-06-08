from datetime import datetime
from uuid import UUID

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    String,
    Text,
    UniqueConstraint,
    Uuid,
    func,
)
from sqlalchemy.dialects.postgresql import ENUM as PostgreSQLEnum
from sqlalchemy.orm import Mapped, mapped_column

from sentinel_common.db import Base
from sentinel_common.models import TimestampMixin, UUIDPrimaryKeyMixin


tenant_status_enum = PostgreSQLEnum(
    "pending_consent",
    "active",
    "suspended",
    "offboarding",
    "offboarded",
    name="tenant_status",
    schema="identity",
    create_type=False,
)


class Tenant(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "tenants"
    __table_args__ = {"schema": "identity"}

    entra_tenant_id: Mapped[UUID] = mapped_column(Uuid, nullable=False)
    identity_scope_key: Mapped[str] = mapped_column(String(128), nullable=False, unique=True)
    account_type: Mapped[str] = mapped_column(String(32), nullable=False, default="organization")
    display_name: Mapped[str] = mapped_column(String(255), nullable=False)
    status: Mapped[str] = mapped_column(tenant_status_enum, nullable=False, default="active")
    consented_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    version: Mapped[int] = mapped_column(nullable=False, default=1)


class User(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "users"
    __table_args__ = (
        UniqueConstraint("tenant_id", "entra_object_id", name="uq_users_tenant_oid"),
        Index("ix_users_tenant_active", "tenant_id", "is_active"),
        {"schema": "identity"},
    )

    tenant_id: Mapped[UUID] = mapped_column(Uuid, ForeignKey("identity.tenants.id"), nullable=False)
    entra_object_id: Mapped[UUID] = mapped_column(Uuid, nullable=False)
    principal_name: Mapped[str | None] = mapped_column(String(320))
    display_name: Mapped[str] = mapped_column(String(255), nullable=False)
    email: Mapped[str | None] = mapped_column(String(320))
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    last_login_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    version: Mapped[int] = mapped_column(nullable=False, default=1)


class Role(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "roles"
    __table_args__ = (
        UniqueConstraint("tenant_id", "name", name="uq_roles_tenant_name"),
        {"schema": "identity"},
    )

    tenant_id: Mapped[UUID] = mapped_column(Uuid, nullable=False)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    is_system: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)


class Permission(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "permissions"
    __table_args__ = {"schema": "identity"}

    name: Mapped[str] = mapped_column(String(128), nullable=False, unique=True)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class RolePermission(Base):
    __tablename__ = "role_permissions"
    __table_args__ = {"schema": "identity"}

    role_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("identity.roles.id", ondelete="CASCADE"), primary_key=True
    )
    permission_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("identity.permissions.id", ondelete="CASCADE"), primary_key=True
    )


class UserRole(Base):
    __tablename__ = "user_roles"
    __table_args__ = (
        Index("ix_user_roles_effective", "tenant_id", "user_id", "expires_at"),
        {"schema": "identity"},
    )

    tenant_id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    user_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("identity.users.id", ondelete="CASCADE"), primary_key=True
    )
    role_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("identity.roles.id", ondelete="CASCADE"), primary_key=True
    )
    scope_type: Mapped[str] = mapped_column(String(32), primary_key=True, default="tenant")
    scope_id: Mapped[str] = mapped_column(String(512), primary_key=True, default="*")
    assigned_by: Mapped[UUID | None] = mapped_column(Uuid)
    assigned_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class OAuthConnection(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "oauth_connections"
    __table_args__ = (
        UniqueConstraint(
            "tenant_id",
            "user_id",
            "provider",
            name="uq_oauth_tenant_user_provider",
        ),
        Index("ix_oauth_connections_tenant_user", "tenant_id", "user_id"),
        {"schema": "identity"},
    )

    tenant_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("identity.tenants.id", ondelete="CASCADE"), nullable=False
    )
    user_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("identity.users.id", ondelete="CASCADE"), nullable=False
    )
    provider: Mapped[str] = mapped_column(String(64), nullable=False, default="microsoft")
    token_authority: Mapped[str] = mapped_column(String(64), nullable=False)
    scopes: Mapped[str] = mapped_column(Text, nullable=False)
    encrypted_refresh_token: Mapped[str] = mapped_column(Text, nullable=False)
    last_refreshed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
