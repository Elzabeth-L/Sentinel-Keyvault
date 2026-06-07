from decimal import Decimal
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class RelationshipResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    source_resource_id: UUID
    target_resource_id: UUID
    relationship_type: str
    dependency_strength: str
    confidence: Decimal
    evidence: dict[str, object]


class GraphQuery(BaseModel):
    root_resource_id: UUID
    direction: Literal["upstream", "downstream", "both"] = "downstream"
    max_depth: int = Field(3, ge=1, le=10)
    max_nodes: int = Field(500, ge=1, le=2000)
    relationship_types: list[str] = Field(default_factory=list, max_length=25)


class GraphNode(BaseModel):
    id: UUID
    label: str
    resource_type: str
    resource_group: str
    azure_resource_id: str


class GraphEdge(BaseModel):
    id: UUID
    source: UUID
    target: UUID
    relationship_type: str
    confidence: float


class GraphResponse(BaseModel):
    root_resource_id: UUID
    truncated: bool
    nodes: list[GraphNode]
    edges: list[GraphEdge]


class ResourceProjectionEvent(BaseModel):
    tenant_id: UUID
    inventory_resource_id: UUID
    azure_resource_id: str
    name: str
    resource_type: str
    resource_group: str
    properties: dict[str, object]
