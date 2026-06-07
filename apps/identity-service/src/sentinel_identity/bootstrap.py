from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from sentinel_common.config import Settings
from sentinel_identity.account import identity_scope_key
from sentinel_identity.models import Permission, Role, RolePermission, Tenant, User, UserRole

PERMISSIONS = {
    "tenant.onboarding.manage": "Manage tenant onboarding",
    "identity.roles.read": "Read roles and permissions",
    "identity.roles.assign": "Assign internal roles",
    "inventory.resources.read": "Read Azure resource inventory",
    "inventory.sync.execute": "Run Azure inventory synchronization",
    "relationships.read": "Read dependency relationships",
    "analysis.create": "Create change assessments",
    "analysis.read": "Read change assessments",
    "operations.create": "Create governed operations",
    "operations.approve": "Approve governed operations",
    "operations.execute": "Execute approved operations",
    "operations.cancel": "Cancel operations",
    "audit.read": "Read audit evidence",
    "audit.export": "Export audit evidence",
    "settings.manage": "Manage tenant settings",
}


async def bootstrap_identity(session: AsyncSession, settings: Settings) -> None:
    permissions: dict[str, Permission] = {}
    for name, description in PERMISSIONS.items():
        permission = await session.scalar(select(Permission).where(Permission.name == name))
        if permission is None:
            permission = Permission(name=name, description=description)
            session.add(permission)
            await session.flush()
        permissions[name] = permission

    if not settings.bootstrap_tenant_id:
        return
    entra_tenant_id = UUID(settings.bootstrap_tenant_id)
    scope_key = identity_scope_key(entra_tenant_id, UUID(int=0))
    tenant = await session.scalar(
        select(Tenant).where(Tenant.identity_scope_key == scope_key)
    )
    if tenant is None:
        tenant = Tenant(
            entra_tenant_id=entra_tenant_id,
            identity_scope_key=scope_key,
            account_type="organization",
            display_name=settings.bootstrap_tenant_name,
            status="active",
        )
        session.add(tenant)
        await session.flush()
    admin_role = await session.scalar(
        select(Role).where(Role.tenant_id == tenant.id, Role.name == "TenantAdministrator")
    )
    if admin_role is None:
        admin_role = Role(
            tenant_id=tenant.id,
            name="TenantAdministrator",
            description="Full Sentinel administration within one tenant",
            is_system=True,
        )
        session.add(admin_role)
        await session.flush()
    for permission in permissions.values():
        if await session.get(RolePermission, (admin_role.id, permission.id)) is None:
            session.add(RolePermission(role_id=admin_role.id, permission_id=permission.id))

    if settings.bootstrap_admin_object_id:
        object_id = UUID(settings.bootstrap_admin_object_id)
        user = await session.scalar(
            select(User).where(
                User.tenant_id == tenant.id,
                User.entra_object_id == object_id,
            )
        )
        if user is None:
            user = User(
                tenant_id=tenant.id,
                entra_object_id=object_id,
                display_name=settings.bootstrap_admin_name,
                is_active=True,
            )
            session.add(user)
            await session.flush()
        key = (tenant.id, user.id, admin_role.id, "tenant", "*")
        if await session.get(UserRole, key) is None:
            session.add(
                UserRole(
                    tenant_id=tenant.id,
                    user_id=user.id,
                    role_id=admin_role.id,
                    scope_type="tenant",
                    scope_id="*",
                )
            )
