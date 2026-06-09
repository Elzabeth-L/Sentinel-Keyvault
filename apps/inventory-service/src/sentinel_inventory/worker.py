import asyncio
import logging
from datetime import UTC, datetime
from uuid import UUID

import httpx

from sentinel_common.config import get_settings
from sentinel_common.db import create_engine, create_session_factory
from sentinel_common.http import configure_logging
from sentinel_inventory.azure import IdentityDelegatedCredential, ResourceGraphInventoryProvider
from sentinel_inventory.repository import InventoryRepository

logger = logging.getLogger(__name__)


async def run_once() -> bool:
    settings = get_settings().model_copy(update={"service_name": "inventory-worker"})
    engine = create_engine(settings)
    session_factory = create_session_factory(engine)
    try:
        async with session_factory() as session:
            async with session.begin():
                repository = InventoryRepository(session)
                job = await repository.claim_job()
            if job is None:
                return False

        try:
            subscription_ids = [UUID(str(item)) for item in job.scope["subscription_ids"]]
            entra_tenant_id = UUID(str(job.scope["entra_tenant_id"]))
            provider = ResourceGraphInventoryProvider(
                settings,
                entra_tenant_id,
                IdentityDelegatedCredential(settings, job.tenant_id, job.requested_by),
            )
            available = {item.subscription_id: item for item in await provider.list_subscriptions()}
            async with session_factory() as session:
                async with session.begin():
                    repository = InventoryRepository(session)
                    subscriptions = {}
                    for subscription_id in subscription_ids:
                        source = available.get(subscription_id)
                        if source is None:
                            raise PermissionError(
                                f"Subscription {subscription_id} is not accessible"
                            )
                        subscriptions[subscription_id] = await repository.upsert_subscription(
                            job.tenant_id,
                            source.subscription_id,
                            source.display_name,
                            source.state,
                        )

            resources = await provider.query_resources(subscription_ids)
            changed = 0
            projections: list[dict[str, object]] = []
            async with session_factory() as session:
                async with session.begin():
                    repository = InventoryRepository(session)
                    for item in resources:
                        subscription_id = UUID(str(item["subscriptionId"]))
                        resource, was_changed = await repository.upsert_resource(
                            job.tenant_id, subscriptions[subscription_id], item
                        )
                        changed += int(was_changed)
                        projections.append(
                            {
                                "tenant_id": str(job.tenant_id),
                                "inventory_resource_id": str(resource.id),
                                "azure_resource_id": resource.azure_resource_id,
                                "name": resource.name,
                                "resource_type": resource.resource_type,
                                "resource_group": resource.resource_group,
                                "properties": resource.properties,
                            }
                        )
                    persisted_job = await session.get(type(job), job.id, with_for_update=True)
                    if persisted_job:
                        persisted_job.status = "completed"
                        persisted_job.resources_seen = len(resources)
                        persisted_job.resources_changed = changed
                        persisted_job.completed_at = datetime.now(UTC)
                        persisted_job.heartbeat_at = persisted_job.completed_at
            async with httpx.AsyncClient(timeout=10.0) as client:
                for projection in projections:
                    response = await client.post(
                        f"{str(settings.relationship_service_url).rstrip('/')}/api/v1/internal/resources",
                        json=projection,
                        headers={"X-Internal-Token": settings.internal_api_token or ""},
                    )
                    response.raise_for_status()
                rebuild = await client.post(
                    (
                        f"{str(settings.relationship_service_url).rstrip('/')}"
                        f"/api/v1/internal/rebuild/{job.tenant_id}"
                    ),
                    headers={"X-Internal-Token": settings.internal_api_token or ""},
                )
                rebuild.raise_for_status()
            return True
        except Exception as exc:
            logger.exception("inventory_sync_failed", extra={"job_id": str(job.id)})
            async with session_factory() as session:
                async with session.begin():
                    persisted_job = await session.get(type(job), job.id, with_for_update=True)
                    if persisted_job:
                        persisted_job.status = "failed"
                        persisted_job.error_summary = {
                            "type": type(exc).__name__,
                            "message": str(exc),
                        }
                        persisted_job.completed_at = datetime.now(UTC)
            return True
    finally:
        await engine.dispose()


async def main() -> None:
    settings = get_settings().model_copy(update={"service_name": "inventory-worker"})
    configure_logging(settings)
    while True:
        worked = await run_once()
        if not worked:
            await asyncio.sleep(5)


if __name__ == "__main__":
    asyncio.run(main())
