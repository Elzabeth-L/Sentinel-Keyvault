from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class AssessmentCreate(BaseModel):
    action_type: str = Field(min_length=3, max_length=255)
    target_resource_id: UUID
    parameters: dict[str, object] = Field(default_factory=dict)


class AssessmentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    target_resource_id: UUID
    action_type: str
    status: str
    risk_score: int | None
    risk_level: str | None
    approval_required: bool | None
    rule_set_version: str | None
    input_sha256: str
    assessed_at: datetime | None
    expires_at: datetime | None
    failure_code: str | None
