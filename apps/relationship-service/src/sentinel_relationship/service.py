from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from sentinel_relationship.extractors import DEFAULT_EXTRACTORS
from sentinel_relationship.repository import RelationshipRepository
from sentinel_relationship.schemas import GraphEdge, GraphNode, GraphQuery, GraphResponse


class RelationshipService:
    def __init__(self, session: AsyncSession) -> None:
        self.repository = RelationshipRepository(session)

    async def project_and_extract(self, event) -> int:
        node = await self.repository.upsert_node(
            tenant_id=event.tenant_id,
            inventory_resource_id=event.inventory_resource_id,
            azure_resource_id=event.azure_resource_id,
            name=event.name,
            resource_type=event.resource_type,
            resource_group=event.resource_group,
            properties=event.properties,
        )
        changed = 0
        for extractor in DEFAULT_EXTRACTORS:
            if extractor.supports(node.resource_type):
                changed += await self.repository.rebuild_edges(
                    event.tenant_id, node, extractor, extractor.extract(node.properties)
                )
        return changed

    async def rebuild_all(self, tenant_id: UUID) -> int:
        changed = 0
        for node in await self.repository.list_nodes(tenant_id):
            for extractor in DEFAULT_EXTRACTORS:
                if extractor.supports(node.resource_type):
                    changed += await self.repository.rebuild_edges(
                        tenant_id,
                        node,
                        extractor,
                        extractor.extract(node.properties),
                    )
        return changed

    async def graph(self, tenant_id: UUID, query: GraphQuery) -> GraphResponse:
        frontier = {query.root_resource_id}
        visited = {query.root_resource_id}
        edges_by_id = {}
        truncated = False
        for _ in range(query.max_depth):
            next_frontier: set[UUID] = set()
            edges = await self.repository.edges_for_frontier(tenant_id, frontier, query.direction)
            for edge in edges:
                if (
                    query.relationship_types
                    and edge.relationship_type not in query.relationship_types
                ):
                    continue
                edges_by_id[edge.id] = edge
                next_frontier.update((edge.source_resource_id, edge.target_resource_id))
                if len(visited | next_frontier) >= query.max_nodes:
                    truncated = True
                    break
            next_frontier -= visited
            visited |= next_frontier
            frontier = next_frontier
            if truncated or not frontier:
                break
        nodes = await self.repository.get_nodes(tenant_id, visited)
        return GraphResponse(
            root_resource_id=query.root_resource_id,
            truncated=truncated,
            nodes=[
                GraphNode(
                    id=item.inventory_resource_id,
                    label=item.name,
                    resource_type=item.resource_type,
                    resource_group=item.resource_group,
                    azure_resource_id=item.azure_resource_id,
                )
                for item in nodes
            ],
            edges=[
                GraphEdge(
                    id=item.id,
                    source=item.source_resource_id,
                    target=item.target_resource_id,
                    relationship_type=item.relationship_type,
                    confidence=float(item.confidence),
                )
                for item in edges_by_id.values()
                if item.source_resource_id in visited and item.target_resource_id in visited
            ],
        )
