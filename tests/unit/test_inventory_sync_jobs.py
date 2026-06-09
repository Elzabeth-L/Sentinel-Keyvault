from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest
from sentinel_inventory.repository import InventoryRepository


@pytest.mark.asyncio
async def test_create_sync_job_persists_entra_tenant_in_scope() -> None:
    session = MagicMock()
    session.scalar = AsyncMock()
    session.flush = AsyncMock()
    session.scalar.return_value = None
    repository = InventoryRepository(session)
    tenant_id = uuid4()
    actor_id = uuid4()
    entra_tenant_id = uuid4()
    subscription_id = uuid4()

    job = await repository.create_sync_job(
        tenant_id,
        actor_id,
        entra_tenant_id,
        "incremental",
        [subscription_id],
        uuid4(),
        "test-idempotency-key",
    )

    assert job.scope == {
        "subscription_ids": [str(subscription_id)],
        "entra_tenant_id": str(entra_tenant_id),
    }
    session.add.assert_called_once_with(job)
    session.flush.assert_awaited_once()
