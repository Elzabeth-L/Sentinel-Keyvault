from uuid import UUID

from pydantic import BaseModel, ConfigDict


class PermissionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    name: str
    description: str


class RoleResponse(BaseModel):
    id: UUID
    name: str
    description: str | None
    permissions: list[str]


class ProfileResponse(BaseModel):
    user_id: UUID
    tenant_id: UUID
    entra_tenant_id: UUID
    entra_object_id: UUID
    display_name: str
    principal_name: str | None
    roles: list[str]
    permissions: list[str]


class LoginResponse(BaseModel):
    authorization_url: str


class AzureAccessTokenResponse(BaseModel):
    access_token: str
    expires_in: int
