from dataclasses import dataclass
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from sentinel_common.auth import TokenPrincipal
from sentinel_identity.account import identity_scope_key, is_personal_account
from sentinel_identity.models import Permission, Role, Tenant, User
from sentinel_identity.repository import IdentityRepository


@dataclass(frozen=True, slots=True)
class ResolvedIdentity:
    tenant: Tenant
    user: User
    roles: tuple[Role, ...]
    permissions: tuple[Permission, ...]


class IdentityService:
    def __init__(self, session: AsyncSession) -> None:
        self._repository = IdentityRepository(session)

    async def resolve_and_sync(self, principal: TokenPrincipal) -> ResolvedIdentity:
        tenant = await self._repository.get_tenant_by_scope_key(
            identity_scope_key(principal.entra_tenant_id, principal.entra_object_id)
        )
        if tenant is None:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Tenant has not been onboarded",
            )
        if tenant.status != "active":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Tenant is not active",
            )
        user = await self._repository.synchronize_user(
            tenant.id,
            principal.entra_object_id,
            principal.display_name,
            principal.principal_name,
        )
        if not user.is_active:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="User is disabled")
        roles = await self._repository.effective_roles(tenant.id, user.id)
        permissions = await self._repository.effective_permissions(tenant.id, user.id)
        return ResolvedIdentity(tenant, user, tuple(roles), tuple(permissions))

    async def onboard_oauth_user(
        self,
        principal: TokenPrincipal,
        tenant_display_name: str | None,
        encrypted_refresh_token: str,
        scopes: tuple[str, ...],
        token_authority: str,
    ) -> ResolvedIdentity:
        personal = is_personal_account(principal.entra_tenant_id)
        tenant, created = await self._repository.get_or_create_tenant(
            principal.entra_tenant_id,
            identity_scope_key(principal.entra_tenant_id, principal.entra_object_id),
            "personal" if personal else "organization",
            tenant_display_name or (principal.display_name if personal else None),
        )
        existing_count = await self._repository.count_users(tenant.id)
        user = await self._repository.synchronize_user(
            tenant.id,
            principal.entra_object_id,
            principal.display_name,
            principal.principal_name,
        )
        role_name = "TenantAdministrator" if created or existing_count == 0 else "Reader"
        role = await self._repository.get_or_create_role(
            tenant.id,
            role_name,
            (
                "Full Sentinel administration within one tenant"
                if role_name == "TenantAdministrator"
                else "Read-only Sentinel access"
            ),
        )
        permission_names = (
            {
                "tenant.onboarding.manage",
                "identity.roles.read",
                "identity.roles.assign",
                "inventory.resources.read",
                "inventory.sync.execute",
                "relationships.read",
                "analysis.create",
                "analysis.read",
                "operations.create",
                "operations.approve",
                "operations.execute",
                "operations.cancel",
                "audit.read",
                "audit.export",
                "settings.manage",
            }
            if role_name == "TenantAdministrator"
            else {
                "inventory.resources.read",
                "relationships.read",
                "analysis.read",
                "audit.read",
            }
        )
        await self._repository.grant_permissions(role, permission_names)
        await self._repository.assign_role(tenant.id, user.id, role.id)
        await self._repository.upsert_oauth_connection(
            tenant.id,
            user.id,
            encrypted_refresh_token,
            scopes,
            token_authority,
        )
        roles = await self._repository.effective_roles(tenant.id, user.id)
        permissions = await self._repository.effective_permissions(tenant.id, user.id)
        return ResolvedIdentity(tenant, user, tuple(roles), tuple(permissions))

    async def resolve_session(self, tenant_id: UUID, user_id: UUID) -> ResolvedIdentity:
        user = await self._repository.get_user_by_id(tenant_id, user_id)
        if user is None or not user.is_active:
            raise HTTPException(status_code=401, detail="Session user is not active")
        actual_tenant = await self._repository.get_tenant_by_id(tenant_id)
        if actual_tenant is None or actual_tenant.status != "active":
            raise HTTPException(status_code=403, detail="Tenant is not active")
        roles = await self._repository.effective_roles(tenant_id, user_id)
        permissions = await self._repository.effective_permissions(tenant_id, user_id)
        return ResolvedIdentity(actual_tenant, user, tuple(roles), tuple(permissions))

    async def list_permissions(self) -> list[Permission]:
        return await self._repository.list_permissions()

    async def list_roles(self, tenant_id: UUID) -> list[tuple[Role, list[str]]]:
        return await self._repository.list_roles_with_permissions(tenant_id)
