import base64
from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import Select, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from sentinel_inventory.models import Resource, ResourceGroup, Subscription, SyncJob


class InventoryRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def list_resources(
        self,
        tenant_id: UUID,
        *,
        subscription_id: UUID | None,
        resource_group: str | None,
        resource_type: str | None,
        location: str | None,
        state: str | None,
        search: str | None,
        cursor: str | None,
        limit: int,
    ) -> tuple[list[Resource], str | None]:
        statement: Select[tuple[Resource]] = select(Resource).where(Resource.tenant_id == tenant_id)
        if subscription_id:
            statement = statement.where(Resource.subscription_id == subscription_id)
        if resource_group:
            statement = statement.where(
                func.lower(Resource.resource_group) == resource_group.lower()
            )
        if resource_type:
            statement = statement.where(func.lower(Resource.resource_type) == resource_type.lower())
        if location:
            statement = statement.where(func.lower(Resource.location) == location.lower())
        if state:
            statement = statement.where(Resource.state == state)
        if search:
            pattern = f"%{search.strip()}%"
            statement = statement.where(
                or_(Resource.name.ilike(pattern), Resource.azure_resource_id.ilike(pattern))
            )
        if cursor:
            decoded = UUID(base64.urlsafe_b64decode(cursor.encode()).decode())
            statement = statement.where(Resource.id > decoded)
        rows = list(await self._session.scalars(statement.order_by(Resource.id).limit(limit + 1)))
        next_cursor = None
        if len(rows) > limit:
            next_cursor = base64.urlsafe_b64encode(str(rows[limit - 1].id).encode()).decode()
            rows = rows[:limit]
        return rows, next_cursor

    async def get_resource(self, tenant_id: UUID, resource_id: UUID) -> Resource | None:
        return await self._session.scalar(
            select(Resource).where(Resource.tenant_id == tenant_id, Resource.id == resource_id)
        )

    async def list_subscriptions(self, tenant_id: UUID) -> list[Subscription]:
        return list(
            await self._session.scalars(
                select(Subscription)
                .where(Subscription.tenant_id == tenant_id)
                .order_by(Subscription.display_name)
            )
        )

    async def list_resource_groups(self, tenant_id: UUID) -> list[ResourceGroup]:
        return list(
            await self._session.scalars(
                select(ResourceGroup)
                .where(ResourceGroup.tenant_id == tenant_id)
                .order_by(ResourceGroup.name)
            )
        )

    async def create_sync_job(
        self,
        tenant_id: UUID,
        actor_id: UUID,
        mode: str,
        subscription_ids: list[UUID],
        correlation_id: UUID,
        idempotency_key: str,
    ) -> SyncJob:
        existing = await self._session.scalar(
            select(SyncJob).where(
                SyncJob.tenant_id == tenant_id,
                SyncJob.idempotency_key == idempotency_key,
            )
        )
        if existing:
            return existing
        job = SyncJob(
            tenant_id=tenant_id,
            requested_by=actor_id,
            mode=mode,
            scope={"subscription_ids": [str(item) for item in subscription_ids]},
            correlation_id=correlation_id,
            idempotency_key=idempotency_key,
        )
        self._session.add(job)
        await self._session.flush()
        return job

    async def claim_job(self) -> SyncJob | None:
        job = await self._session.scalar(
            select(SyncJob)
            .where(SyncJob.status == "queued")
            .order_by(SyncJob.requested_at)
            .with_for_update(skip_locked=True)
            .limit(1)
        )
        if job:
            job.status = "running"
            job.started_at = datetime.now(UTC)
            job.heartbeat_at = job.started_at
        return job

    async def find_subscription(
        self, tenant_id: UUID, azure_subscription_id: UUID
    ) -> Subscription | None:
        return await self._session.scalar(
            select(Subscription).where(
                Subscription.tenant_id == tenant_id,
                Subscription.azure_subscription_id == azure_subscription_id,
            )
        )

    async def upsert_subscription(
        self, tenant_id: UUID, azure_subscription_id: UUID, display_name: str, state: str
    ) -> Subscription:
        subscription = await self.find_subscription(tenant_id, azure_subscription_id)
        if subscription is None:
            subscription = Subscription(
                tenant_id=tenant_id,
                azure_subscription_id=azure_subscription_id,
                display_name=display_name,
                state=state,
            )
            self._session.add(subscription)
        else:
            subscription.display_name = display_name
            subscription.state = state
            subscription.version += 1
        await self._session.flush()
        return subscription

    async def upsert_resource(
        self, tenant_id: UUID, subscription: Subscription, item: dict[str, object]
    ) -> tuple[Resource, bool]:
        arm_id = str(item["id"])
        normalized = arm_id.lower()
        resource = await self._session.scalar(
            select(Resource).where(
                Resource.tenant_id == tenant_id,
                Resource.normalized_resource_id == normalized,
            )
        )
        now = datetime.now(UTC)
        changed = resource is None
        values = {
            "azure_resource_id": arm_id,
            "normalized_resource_id": normalized,
            "resource_type": str(item.get("type") or "").lower(),
            "name": str(item.get("name") or ""),
            "resource_group": str(item.get("resourceGroup") or ""),
            "location": item.get("location"),
            "kind": item.get("kind"),
            "sku": str(item.get("sku") or "") or None,
            "tags": item.get("tags") or {},
            "properties": item.get("properties") or {},
            "last_seen_at": now,
            "state": "active",
            "missing_since": None,
        }
        if resource is None:
            resource = Resource(tenant_id=tenant_id, subscription_id=subscription.id, **values)
            self._session.add(resource)
        else:
            for name, value in values.items():
                if getattr(resource, name) != value:
                    changed = True
                    setattr(resource, name, value)
            resource.version += 1
        await self._session.flush()
        if resource.resource_type == "microsoft.resources/subscriptions/resourcegroups":
            group = await self._session.scalar(
                select(ResourceGroup).where(
                    ResourceGroup.tenant_id == tenant_id,
                    ResourceGroup.subscription_id == subscription.id,
                    ResourceGroup.normalized_name == resource.name.lower(),
                )
            )
            if group is None:
                group = ResourceGroup(
                    tenant_id=tenant_id,
                    subscription_id=subscription.id,
                    name=resource.name,
                    normalized_name=resource.name.lower(),
                    location=resource.location,
                    tags=resource.tags,
                )
                self._session.add(group)
            else:
                group.last_seen_at = now
                group.state = "active"
        return resource, changed
