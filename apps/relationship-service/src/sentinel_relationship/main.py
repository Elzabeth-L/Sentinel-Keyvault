from uuid import UUID

from fastapi import Depends, Header, HTTPException, Query

from sentinel_common.audit import enqueue_audit
from sentinel_common.auth import (
    IdentityProfileClient,
    actor_dependency,
    permission_dependency,
)
from sentinel_common.config import get_settings
from sentinel_common.context import ActorContext
from sentinel_common.db import UnitOfWork, create_engine, create_session_factory
from sentinel_common.events import AuditEvent
from sentinel_common.http import create_app
from sentinel_relationship.repository import RelationshipRepository
from sentinel_relationship.schemas import (
    GraphQuery,
    GraphResponse,
    RelationshipResponse,
    ResourceProjectionEvent,
)
from sentinel_relationship.service import RelationshipService

settings = get_settings().model_copy(update={"service_name": "relationship-service"})
engine = create_engine(settings)
session_factory = create_session_factory(engine)
get_actor = actor_dependency(IdentityProfileClient(settings))
read_relationships = permission_dependency(get_actor, "relationships.read")
app = create_app(settings, engine)


@app.get("/api/v1/relationships", response_model=list[RelationshipResponse], tags=["relationships"])
async def relationships(
    resource_id: UUID | None = None,
    direction: str = Query("both", pattern="^(upstream|downstream|both)$"),
    relationship_type: str | None = None,
    minimum_confidence: float = Query(0.0, ge=0.0, le=1.0),
    actor: ActorContext = Depends(read_relationships),
) -> list[RelationshipResponse]:
    async with UnitOfWork(session_factory, actor.tenant_id, actor.actor_id) as uow:
        rows = await RelationshipRepository(uow.session).list_edges(
            actor.tenant_id,
            resource_id,
            direction,
            relationship_type,
            minimum_confidence,
        )
        return [RelationshipResponse.model_validate(item) for item in rows]


@app.post("/api/v1/relationships/graph", response_model=GraphResponse, tags=["relationships"])
@app.post(
    "/api/v1/relationships/graph-queries", response_model=GraphResponse, tags=["relationships"]
)
async def graph(
    query: GraphQuery,
    actor: ActorContext = Depends(read_relationships),
) -> GraphResponse:
    async with UnitOfWork(session_factory, actor.tenant_id, actor.actor_id) as uow:
        result = await RelationshipService(uow.session).graph(actor.tenant_id, query)
        await enqueue_audit(
            uow.session,
            AuditEvent(
                source="relationship-service",
                type="relationships.graph-queried.v1",
                subject=f"resource/{query.root_resource_id}",
                tenant_id=actor.tenant_id,
                correlation_id=actor.correlation_id,
                data={"node_count": len(result.nodes), "edge_count": len(result.edges)},
                actor_type="user",
                actor_id=str(actor.actor_id),
                action="relationships.graph.read",
                entity_type="resource",
                entity_id=str(query.root_resource_id),
                outcome="succeeded",
            ),
        )
        return result


@app.get("/api/v1/relationships/graph", response_model=GraphResponse, tags=["relationships"])
async def graph_get(
    root_resource_id: UUID,
    direction: str = Query("downstream", pattern="^(upstream|downstream|both)$"),
    max_depth: int = Query(3, ge=1, le=10),
    max_nodes: int = Query(500, ge=1, le=2000),
    actor: ActorContext = Depends(read_relationships),
) -> GraphResponse:
    query = GraphQuery(
        root_resource_id=root_resource_id,
        direction=direction,
        max_depth=max_depth,
        max_nodes=max_nodes,
    )
    async with UnitOfWork(session_factory, actor.tenant_id, actor.actor_id) as uow:
        return await RelationshipService(uow.session).graph(actor.tenant_id, query)


@app.post("/api/v1/internal/resources", status_code=204, include_in_schema=False)
async def project_resource(
    event: ResourceProjectionEvent,
    x_internal_token: str | None = Header(None),
) -> None:
    if not settings.internal_api_token or x_internal_token != settings.internal_api_token:
        raise HTTPException(status_code=401, detail="Invalid internal credential")
    async with UnitOfWork(session_factory, event.tenant_id, event.inventory_resource_id) as uow:
        await RelationshipService(uow.session).project_and_extract(event)


@app.post("/api/v1/internal/rebuild/{tenant_id}", status_code=204, include_in_schema=False)
async def rebuild_relationships(
    tenant_id: UUID,
    x_internal_token: str | None = Header(None),
) -> None:
    if not settings.internal_api_token or x_internal_token != settings.internal_api_token:
        raise HTTPException(status_code=401, detail="Invalid internal credential")
    async with UnitOfWork(session_factory, tenant_id, tenant_id) as uow:
        await RelationshipService(uow.session).rebuild_all(tenant_id)
