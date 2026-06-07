from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class AuditLogResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    event_id: UUID
    occurred_at: datetime
    actor_type: str
    actor_id: str
    action: str
    entity_type: str
    entity_id: str | None
    outcome: str
    source_service: str
    correlation_id: UUID
    metadata_json: dict[str, object]
    record_hash: str


class ActivityResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    user_id: UUID | None
    category: str
    message: str
    related_entity_type: str | None
    related_entity_id: str | None
    occurred_at: datetime
