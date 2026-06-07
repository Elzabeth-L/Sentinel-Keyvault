from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class ActionResponse(BaseModel):
    action_type: str
    display_name: str
    required_permission: str
    azure_permissions: list[str]
    destructive: bool
    enabled: bool
    parameter_schema: dict[str, object]


class OperationCreate(BaseModel):
    assessment_id: UUID
    assessment_input_hash: str = Field(pattern="^sha256:[a-f0-9]{64}$")
    action_type: str
    target_resource_id: UUID
    parameters: dict[str, object] = Field(default_factory=dict)
    reason: str = Field(min_length=10, max_length=2000)


class OperationResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    assessment_id: UUID
    action_type: str
    target_resource_id: UUID
    status: str
    reason: str
    version: int
