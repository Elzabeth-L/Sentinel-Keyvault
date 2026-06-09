from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest
from sentinel_inventory.azure import INVENTORY_QUERY
from sentinel_inventory.models import Resource
from sentinel_inventory.repository import InventoryRepository
from sqlalchemy.dialects.postgresql import ENUM


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


def test_resource_state_uses_existing_postgresql_enum() -> None:
    state_type = Resource.__table__.c.state.type

    assert isinstance(state_type, ENUM)
    assert state_type.name == "resource_state"
    assert state_type.schema == "inventory"
    assert state_type.create_type is False


def test_inventory_query_collects_all_resources_and_resource_groups() -> None:
    normalized_query = " ".join(INVENTORY_QUERY.lower().split())

    assert "resources | project" in normalized_query
    assert "where tolower(type) in" not in normalized_query
    assert "resourcecontainers" in normalized_query
    assert "microsoft.resources/subscriptions/resourcegroups" in normalized_query
