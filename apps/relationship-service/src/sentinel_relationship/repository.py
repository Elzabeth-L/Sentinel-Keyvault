from datetime import UTC, datetime
from decimal import Decimal
from uuid import UUID

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from sentinel_relationship.extractors import EdgeCandidate, RelationshipExtractor
from sentinel_relationship.models import Relationship, ResourceNode


class RelationshipRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def upsert_node(
        self,
        *,
        tenant_id: UUID,
        inventory_resource_id: UUID,
        azure_resource_id: str,
        name: str,
        resource_type: str,
        resource_group: str,
        properties: dict[str, object],
    ) -> ResourceNode:
        node = await self._session.scalar(
            select(ResourceNode).where(
                ResourceNode.tenant_id == tenant_id,
                ResourceNode.inventory_resource_id == inventory_resource_id,
            )
        )
        if node is None:
            node = ResourceNode(
                tenant_id=tenant_id,
                inventory_resource_id=inventory_resource_id,
                azure_resource_id=azure_resource_id,
                normalized_resource_id=azure_resource_id.lower(),
                name=name,
                resource_type=resource_type.lower(),
                resource_group=resource_group,
                properties=properties,
            )
            self._session.add(node)
        else:
            node.name = name
            node.resource_type = resource_type.lower()
            node.resource_group = resource_group
            node.properties = properties
            node.is_active = True
        await self._session.flush()
        return node

    async def rebuild_edges(
        self,
        tenant_id: UUID,
        source: ResourceNode,
        extractor: RelationshipExtractor,
        candidates: list[EdgeCandidate],
    ) -> int:
        current = list(
            await self._session.scalars(
                select(Relationship).where(
                    Relationship.tenant_id == tenant_id,
                    Relationship.source_resource_id == source.inventory_resource_id,
                    Relationship.extractor_name == extractor.name,
                )
            )
        )
        for edge in current:
            edge.is_active = False
        changed = 0
        for candidate in candidates:
            target = await self._session.scalar(
                select(ResourceNode).where(
                    ResourceNode.tenant_id == tenant_id,
                    ResourceNode.normalized_resource_id == candidate.target_resource_id,
                )
            )
            if target is None or target.inventory_resource_id == source.inventory_resource_id:
                continue
            edge = next(
                (
                    item
                    for item in current
                    if item.target_resource_id == target.inventory_resource_id
                    and item.relationship_type == candidate.relationship_type
                ),
                None,
            )
            if edge is None:
                edge = Relationship(
                    tenant_id=tenant_id,
                    source_resource_id=source.inventory_resource_id,
                    target_resource_id=target.inventory_resource_id,
                    relationship_type=candidate.relationship_type,
                    source_system="azure-resource-properties",
                    dependency_strength=candidate.dependency_strength,
                    confidence=Decimal(str(candidate.confidence)),
                    evidence={"path": candidate.evidence_path},
                    extractor_name=extractor.name,
                    extractor_version=extractor.version,
                )
                self._session.add(edge)
                changed += 1
            else:
                edge.is_active = True
                edge.last_observed_at = datetime.now(UTC)
                edge.evidence = {"path": candidate.evidence_path}
        return changed

    async def list_edges(
        self,
        tenant_id: UUID,
        resource_id: UUID | None,
        direction: str,
        relationship_type: str | None,
        minimum_confidence: float,
    ) -> list[Relationship]:
        statement = select(Relationship).where(
            Relationship.tenant_id == tenant_id,
            Relationship.is_active.is_(True),
            Relationship.confidence >= Decimal(str(minimum_confidence)),
        )
        if resource_id:
            if direction == "upstream":
                statement = statement.where(Relationship.target_resource_id == resource_id)
            elif direction == "downstream":
                statement = statement.where(Relationship.source_resource_id == resource_id)
            else:
                statement = statement.where(
                    or_(
                        Relationship.source_resource_id == resource_id,
                        Relationship.target_resource_id == resource_id,
                    )
                )
        if relationship_type:
            statement = statement.where(Relationship.relationship_type == relationship_type)
        return list(await self._session.scalars(statement.order_by(Relationship.id).limit(2000)))

    async def get_nodes(self, tenant_id: UUID, ids: set[UUID]) -> list[ResourceNode]:
        if not ids:
            return []
        return list(
            await self._session.scalars(
                select(ResourceNode).where(
                    ResourceNode.tenant_id == tenant_id,
                    ResourceNode.inventory_resource_id.in_(ids),
                )
            )
        )

    async def list_nodes(self, tenant_id: UUID) -> list[ResourceNode]:
        return list(
            await self._session.scalars(
                select(ResourceNode).where(
                    ResourceNode.tenant_id == tenant_id,
                    ResourceNode.is_active.is_(True),
                )
            )
        )

    async def edges_for_frontier(
        self,
        tenant_id: UUID,
        frontier: set[UUID],
        direction: str,
    ) -> list[Relationship]:
        statement = select(Relationship).where(
            Relationship.tenant_id == tenant_id,
            Relationship.is_active.is_(True),
        )
        if direction == "downstream":
            statement = statement.where(Relationship.source_resource_id.in_(frontier))
        elif direction == "upstream":
            statement = statement.where(Relationship.target_resource_id.in_(frontier))
        else:
            statement = statement.where(
                or_(
                    Relationship.source_resource_id.in_(frontier),
                    Relationship.target_resource_id.in_(frontier),
                )
            )
        return list(await self._session.scalars(statement))
