from uuid import UUID

from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from sentinel_inventory.repository import InventoryRepository


class InventoryService:
    def __init__(self, session: AsyncSession) -> None:
        self.repository = InventoryRepository(session)

    async def resource_or_404(self, tenant_id: UUID, resource_id: UUID):
        resource = await self.repository.get_resource(tenant_id, resource_id)
        if resource is None:
            raise HTTPException(status_code=404, detail="Resource not found")
        return resource
