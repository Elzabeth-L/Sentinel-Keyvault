from datetime import datetime
from uuid import UUID

from fastapi import Depends, Header, HTTPException, Query

from sentinel_audit.repository import AuditRepository
from sentinel_audit.schemas import AuditLogResponse
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

settings = get_settings().model_copy(update={"service_name": "audit-service"})
engine = create_engine(settings)
session_factory = create_session_factory(engine)
get_actor = actor_dependency(IdentityProfileClient(settings))
read_audit = permission_dependency(get_actor, "audit.read")
app = create_app(settings, engine)


@app.post("/api/v1/internal/events", status_code=204, include_in_schema=False)
async def ingest_event(
    event: AuditEvent,
    x_internal_token: str | None = Header(None),
) -> None:
    if not settings.internal_api_token or x_internal_token != settings.internal_api_token:
        raise HTTPException(status_code=401, detail="Invalid internal credential")
    async with UnitOfWork(session_factory, event.tenant_id, event.id) as uow:
        await AuditRepository(uow.session).ingest(event)


@app.get("/api/v1/audit/events", response_model=list[AuditLogResponse], tags=["audit"])
async def events(
    start: datetime | None = None,
    end: datetime | None = None,
    actor_id: str | None = None,
    action: str | None = None,
    entity_type: str | None = None,
    entity_id: str | None = None,
    outcome: str | None = None,
    correlation_id: UUID | None = None,
    limit: int = Query(100, ge=1, le=1000),
    actor: ActorContext = Depends(read_audit),
) -> list[AuditLogResponse]:
    async with UnitOfWork(session_factory, actor.tenant_id, actor.actor_id) as uow:
        rows = await AuditRepository(uow.session).search(
            actor.tenant_id,
            start=start,
            end=end,
            actor_id=actor_id,
            action=action,
            entity_type=entity_type,
            entity_id=entity_id,
            outcome=outcome,
            correlation_id=correlation_id,
            limit=limit,
        )
        return [AuditLogResponse.model_validate(item) for item in rows]


@app.get(
    "/api/v1/audit/operations/{operation_id}",
    response_model=list[AuditLogResponse],
    tags=["audit"],
)
async def operation_timeline(
    operation_id: UUID,
    actor: ActorContext = Depends(read_audit),
) -> list[AuditLogResponse]:
    async with UnitOfWork(session_factory, actor.tenant_id, actor.actor_id) as uow:
        rows = await AuditRepository(uow.session).search(
            actor.tenant_id,
            start=None,
            end=None,
            actor_id=None,
            action=None,
            entity_type="operation",
            entity_id=str(operation_id),
            outcome=None,
            correlation_id=None,
            limit=1000,
        )
        return [AuditLogResponse.model_validate(item) for item in reversed(rows)]
