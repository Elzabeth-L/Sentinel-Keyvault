from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class Page(BaseModel):
    next_cursor: str | None
    limit: int


class ResourceResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    subscription_id: UUID
    azure_resource_id: str
    resource_type: str
    name: str
    resource_group: str
    location: str | None
    kind: str | None
    sku: str | None
    tags: dict[str, str]
    properties: dict[str, object]
    provisioning_state: str | None
    state: str
    last_seen_at: datetime


class ResourcePage(BaseModel):
    items: list[ResourceResponse]
    page: Page


class SubscriptionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    azure_subscription_id: UUID
    display_name: str
    state: str
    last_sync_at: datetime | None


class ResourceGroupResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    subscription_id: UUID
    name: str
    location: str | None
    tags: dict[str, str]
    state: str


class SyncScope(BaseModel):
    subscription_ids: list[UUID] = Field(min_length=1, max_length=100)


class SyncJobCreate(BaseModel):
    scope: SyncScope
    mode: Literal["full", "incremental"] = "incremental"


class SyncJobResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    mode: str
    status: str
    resources_seen: int
    resources_changed: int
    requested_at: datetime
    started_at: datetime | None
    completed_at: datetime | None
    error_summary: dict[str, object] | None
