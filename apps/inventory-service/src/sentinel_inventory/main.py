from uuid import UUID

from fastapi import Depends, Header, HTTPException, Query, status

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
from sentinel_inventory.azure import IdentityDelegatedCredential, ResourceGraphInventoryProvider
from sentinel_inventory.repository import InventoryRepository
from sentinel_inventory.schemas import (
    Page,
    ResourceGroupResponse,
    ResourcePage,
    ResourceResponse,
    SubscriptionResponse,
    SyncJobCreate,
    SyncJobResponse,
)
from sentinel_inventory.service import InventoryService

settings = get_settings().model_copy(update={"service_name": "inventory-service"})
engine = create_engine(settings)
session_factory = create_session_factory(engine)
get_actor = actor_dependency(IdentityProfileClient(settings))
read_inventory = permission_dependency(get_actor, "inventory.resources.read")
sync_inventory = permission_dependency(get_actor, "inventory.sync.execute")
app = create_app(settings, engine)


@app.get("/api/v1/inventory/resources", response_model=ResourcePage, tags=["inventory"])
async def list_resources(
    subscription_id: UUID | None = None,
    resource_group: str | None = None,
    resource_type: str | None = None,
    location: str | None = None,
    state_filter: str | None = Query(None, alias="state"),
    search: str | None = None,
    cursor: str | None = None,
    limit: int = Query(50, ge=1, le=200),
    actor: ActorContext = Depends(read_inventory),
) -> ResourcePage:
    async with UnitOfWork(session_factory, actor.tenant_id, actor.actor_id) as uow:
        rows, next_cursor = await InventoryRepository(uow.session).list_resources(
            actor.tenant_id,
            subscription_id=subscription_id,
            resource_group=resource_group,
            resource_type=resource_type,
            location=location,
            state=state_filter,
            search=search,
            cursor=cursor,
            limit=limit,
        )
    return ResourcePage(
        items=[ResourceResponse.model_validate(item) for item in rows],
        page=Page(next_cursor=next_cursor, limit=limit),
    )


@app.get(
    "/api/v1/inventory/resources/{resource_id}",
    response_model=ResourceResponse,
    tags=["inventory"],
)
async def get_resource(
    resource_id: UUID,
    actor: ActorContext = Depends(read_inventory),
) -> ResourceResponse:
    async with UnitOfWork(session_factory, actor.tenant_id, actor.actor_id) as uow:
        resource = await InventoryService(uow.session).resource_or_404(actor.tenant_id, resource_id)
        return ResourceResponse.model_validate(resource)


@app.get(
    "/api/v1/inventory/subscriptions",
    response_model=list[SubscriptionResponse],
    tags=["inventory"],
)
async def subscriptions(
    actor: ActorContext = Depends(read_inventory),
) -> list[SubscriptionResponse]:
    async with UnitOfWork(session_factory, actor.tenant_id, actor.actor_id) as uow:
        rows = await InventoryRepository(uow.session).list_subscriptions(actor.tenant_id)
        return [SubscriptionResponse.model_validate(item) for item in rows]


@app.post(
    "/api/v1/inventory/subscriptions/discover",
    response_model=list[SubscriptionResponse],
    tags=["inventory"],
)
async def discover_subscriptions(
    actor: ActorContext = Depends(sync_inventory),
) -> list[SubscriptionResponse]:
    provider = ResourceGraphInventoryProvider(
        settings,
        actor.entra_tenant_id,
        IdentityDelegatedCredential(settings, actor.tenant_id, actor.actor_id),
    )
    discovered = await provider.list_subscriptions()
    async with UnitOfWork(session_factory, actor.tenant_id, actor.actor_id) as uow:
        repository = InventoryRepository(uow.session)
        rows = [
            await repository.upsert_subscription(
                actor.tenant_id,
                item.subscription_id,
                item.display_name,
                item.state,
            )
            for item in discovered
        ]
        return [SubscriptionResponse.model_validate(item) for item in rows]


@app.get(
    "/api/v1/inventory/resource-groups",
    response_model=list[ResourceGroupResponse],
    tags=["inventory"],
)
async def resource_groups(
    actor: ActorContext = Depends(read_inventory),
) -> list[ResourceGroupResponse]:
    async with UnitOfWork(session_factory, actor.tenant_id, actor.actor_id) as uow:
        rows = await InventoryRepository(uow.session).list_resource_groups(actor.tenant_id)
        return [ResourceGroupResponse.model_validate(item) for item in rows]


@app.post(
    "/api/v1/inventory/sync-jobs",
    response_model=SyncJobResponse,
    status_code=status.HTTP_202_ACCEPTED,
    tags=["inventory"],
)
async def create_sync_job(
    request: SyncJobCreate,
    idempotency_key: str = Header(min_length=8, max_length=255, alias="Idempotency-Key"),
    actor: ActorContext = Depends(sync_inventory),
) -> SyncJobResponse:
    async with UnitOfWork(session_factory, actor.tenant_id, actor.actor_id) as uow:
        repository = InventoryRepository(uow.session)
        registered = {
            item.azure_subscription_id: item
            for item in await repository.list_subscriptions(actor.tenant_id)
        }
        unknown = [item for item in request.scope.subscription_ids if item not in registered]
        if unknown:
            raise HTTPException(status_code=422, detail="Scope contains unregistered subscriptions")
        job = await repository.create_sync_job(
            actor.tenant_id,
            actor.actor_id,
            request.mode,
            request.scope.subscription_ids,
            actor.correlation_id,
            idempotency_key,
        )
        job.scope["entra_tenant_id"] = str(actor.entra_tenant_id)
        await enqueue_audit(
            uow.session,
            AuditEvent(
                source="inventory-service",
                type="inventory.sync-requested.v1",
                subject=f"sync-job/{job.id}",
                tenant_id=actor.tenant_id,
                correlation_id=actor.correlation_id,
                data={
                    "mode": request.mode,
                    "subscription_count": len(request.scope.subscription_ids),
                },
                actor_type="user",
                actor_id=str(actor.actor_id),
                action="inventory.sync.request",
                entity_type="sync_job",
                entity_id=str(job.id),
                outcome="accepted",
            ),
        )
        return SyncJobResponse.model_validate(job)
