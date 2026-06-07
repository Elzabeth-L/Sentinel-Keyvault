from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4

from pydantic import BaseModel, Field


class CloudEvent(BaseModel):
    specversion: str = "1.0"
    id: UUID = Field(default_factory=uuid4)
    source: str
    type: str
    subject: str
    time: datetime = Field(default_factory=lambda: datetime.now(UTC))
    datacontenttype: str = "application/json"
    tenant_id: UUID
    correlation_id: UUID
    data: dict[str, Any]


class AuditEvent(CloudEvent):
    actor_type: str
    actor_id: str
    action: str
    entity_type: str
    entity_id: str | None = None
    outcome: str
