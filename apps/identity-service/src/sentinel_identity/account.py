from uuid import UUID

MICROSOFT_CONSUMER_TENANT_ID = UUID("9188040d-6c67-4c5b-b112-36a304b66dad")


def is_personal_account(entra_tenant_id: UUID) -> bool:
    return entra_tenant_id == MICROSOFT_CONSUMER_TENANT_ID


def identity_scope_key(entra_tenant_id: UUID, entra_object_id: UUID) -> str:
    if is_personal_account(entra_tenant_id):
        return f"personal:{entra_tenant_id}:{entra_object_id}"
    return f"tenant:{entra_tenant_id}"


def refresh_authority(
    entra_tenant_id: UUID,
    requested_tenant: str | None,
) -> str:
    if is_personal_account(entra_tenant_id):
        return "common"
    return requested_tenant or str(entra_tenant_id)
