from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from sentinel_identity.models import (
    OAuthConnection,
    Permission,
    Role,
    RolePermission,
    Tenant,
    User,
    UserRole,
)


class IdentityRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_tenant_by_scope_key(self, scope_key: str) -> Tenant | None:
        return await self._session.scalar(
            select(Tenant).where(Tenant.identity_scope_key == scope_key)
        )

    async def get_tenant_by_id(self, tenant_id: UUID) -> Tenant | None:
        return await self._session.get(Tenant, tenant_id)

    async def get_or_create_tenant(
        self,
        entra_tenant_id: UUID,
        scope_key: str,
        account_type: str,
        display_name: str | None,
    ) -> tuple[Tenant, bool]:
        tenant = await self.get_tenant_by_scope_key(scope_key)
        if tenant is not None:
            if display_name and tenant.display_name != display_name:
                tenant.display_name = display_name
            return tenant, False
        tenant = Tenant(
            entra_tenant_id=entra_tenant_id,
            identity_scope_key=scope_key,
            account_type=account_type,
            display_name=display_name or str(entra_tenant_id),
            status="active",
            consented_at=datetime.now(UTC),
        )
        self._session.add(tenant)
        await self._session.flush()
        return tenant, True

    async def get_user(self, tenant_id: UUID, entra_object_id: UUID) -> User | None:
        return await self._session.scalar(
            select(User).where(
                User.tenant_id == tenant_id,
                User.entra_object_id == entra_object_id,
            )
        )

    async def synchronize_user(
        self,
        tenant_id: UUID,
        entra_object_id: UUID,
        display_name: str,
        principal_name: str | None,
    ) -> User:
        user = await self.get_user(tenant_id, entra_object_id)
        if user is None:
            user = User(
                tenant_id=tenant_id,
                entra_object_id=entra_object_id,
                display_name=display_name,
                principal_name=principal_name,
                email=principal_name,
            )
            self._session.add(user)
        else:
            user.display_name = display_name
            user.principal_name = principal_name
            user.email = principal_name
            user.last_login_at = datetime.now(UTC)
            user.version += 1
        await self._session.flush()
        return user

    async def get_user_by_id(self, tenant_id: UUID, user_id: UUID) -> User | None:
        return await self._session.scalar(
            select(User).where(User.tenant_id == tenant_id, User.id == user_id)
        )

    async def count_users(self, tenant_id: UUID) -> int:
        from sqlalchemy import func

        return int(
            await self._session.scalar(
                select(func.count(User.id)).where(User.tenant_id == tenant_id)
            )
            or 0
        )

    async def get_or_create_role(self, tenant_id: UUID, name: str, description: str) -> Role:
        role = await self._session.scalar(
            select(Role).where(Role.tenant_id == tenant_id, Role.name == name)
        )
        if role is None:
            role = Role(
                tenant_id=tenant_id,
                name=name,
                description=description,
                is_system=True,
            )
            self._session.add(role)
            await self._session.flush()
        return role

    async def grant_permissions(self, role: Role, permission_names: set[str]) -> None:
        permissions = list(
            await self._session.scalars(
                select(Permission).where(Permission.name.in_(permission_names))
            )
        )
        for permission in permissions:
            existing = await self._session.get(RolePermission, (role.id, permission.id))
            if existing is None:
                self._session.add(RolePermission(role_id=role.id, permission_id=permission.id))

    async def assign_role(self, tenant_id: UUID, user_id: UUID, role_id: UUID) -> None:
        key = (tenant_id, user_id, role_id, "tenant", "*")
        if await self._session.get(UserRole, key) is None:
            self._session.add(
                UserRole(
                    tenant_id=tenant_id,
                    user_id=user_id,
                    role_id=role_id,
                    scope_type="tenant",
                    scope_id="*",
                )
            )

    async def upsert_oauth_connection(
        self,
        tenant_id: UUID,
        user_id: UUID,
        encrypted_refresh_token: str,
        scopes: tuple[str, ...],
        token_authority: str,
    ) -> OAuthConnection:
        connection = await self._session.scalar(
            select(OAuthConnection).where(
                OAuthConnection.tenant_id == tenant_id,
                OAuthConnection.user_id == user_id,
                OAuthConnection.provider == "microsoft",
            )
        )
        if connection is None:
            connection = OAuthConnection(
                tenant_id=tenant_id,
                user_id=user_id,
                provider="microsoft",
                token_authority=token_authority,
                scopes=" ".join(scopes),
                encrypted_refresh_token=encrypted_refresh_token,
            )
            self._session.add(connection)
        else:
            connection.scopes = " ".join(scopes)
            connection.token_authority = token_authority
            connection.encrypted_refresh_token = encrypted_refresh_token
            connection.last_refreshed_at = datetime.now(UTC)
        await self._session.flush()
        return connection

    async def get_oauth_connection(
        self, tenant_id: UUID, user_id: UUID | None = None
    ) -> OAuthConnection | None:
        statement = select(OAuthConnection).where(
            OAuthConnection.tenant_id == tenant_id,
            OAuthConnection.provider == "microsoft",
        )
        if user_id is not None:
            statement = statement.where(OAuthConnection.user_id == user_id)
        return await self._session.scalar(
            statement.order_by(OAuthConnection.updated_at.desc()).limit(1)
        )

    async def effective_roles(self, tenant_id: UUID, user_id: UUID) -> list[Role]:
        now = datetime.now(UTC)
        result = await self._session.scalars(
            select(Role)
            .join(UserRole, UserRole.role_id == Role.id)
            .where(
                UserRole.tenant_id == tenant_id,
                UserRole.user_id == user_id,
                or_(UserRole.expires_at.is_(None), UserRole.expires_at > now),
            )
            .order_by(Role.name)
        )
        return list(result.unique())

    async def effective_permissions(self, tenant_id: UUID, user_id: UUID) -> list[Permission]:
        now = datetime.now(UTC)
        result = await self._session.scalars(
            select(Permission)
            .join(RolePermission, RolePermission.permission_id == Permission.id)
            .join(Role, Role.id == RolePermission.role_id)
            .join(UserRole, UserRole.role_id == Role.id)
            .where(
                UserRole.tenant_id == tenant_id,
                UserRole.user_id == user_id,
                or_(UserRole.expires_at.is_(None), UserRole.expires_at > now),
            )
            .order_by(Permission.name)
        )
        return list(result.unique())

    async def list_permissions(self) -> list[Permission]:
        return list(await self._session.scalars(select(Permission).order_by(Permission.name)))

    async def list_roles_with_permissions(self, tenant_id: UUID) -> list[tuple[Role, list[str]]]:
        roles = list(
            await self._session.scalars(
                select(Role).where(Role.tenant_id == tenant_id).order_by(Role.name)
            )
        )
        output: list[tuple[Role, list[str]]] = []
        for role in roles:
            permissions = list(
                await self._session.scalars(
                    select(Permission.name)
                    .join(RolePermission, RolePermission.permission_id == Permission.id)
                    .where(RolePermission.role_id == role.id)
                    .order_by(Permission.name)
                )
            )
            output.append((role, permissions))
        return output
