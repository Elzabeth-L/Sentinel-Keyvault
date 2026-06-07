import hashlib
import json
from datetime import datetime
from uuid import UUID

from sqlalchemy import Select, desc, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from sentinel_audit.models import ActivityEvent, AuditLog
from sentinel_common.events import AuditEvent


class AuditRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def ingest(self, event: AuditEvent) -> AuditLog:
        existing = await self._session.scalar(
            select(AuditLog).where(
                AuditLog.tenant_id == event.tenant_id,
                AuditLog.event_id == event.id,
            )
        )
        if existing:
            return existing
        await self._session.execute(
            text("SELECT pg_advisory_xact_lock(hashtext(:tenant_id))"),
            {"tenant_id": str(event.tenant_id)},
        )
        previous = await self._session.scalar(
            select(AuditLog)
            .where(AuditLog.tenant_id == event.tenant_id)
            .order_by(desc(AuditLog.ingested_at), desc(AuditLog.id))
            .limit(1)
        )
        previous_hash = previous.record_hash if previous else None
        canonical = {
            "event_id": str(event.id),
            "tenant_id": str(event.tenant_id),
            "occurred_at": event.time.isoformat(),
            "actor_type": event.actor_type,
            "actor_id": event.actor_id,
            "action": event.action,
            "entity_type": event.entity_type,
            "entity_id": event.entity_id,
            "outcome": event.outcome,
            "source": event.source,
            "correlation_id": str(event.correlation_id),
            "data": event.data,
            "previous_hash": previous_hash,
        }
        record_hash = hashlib.sha256(
            json.dumps(canonical, sort_keys=True, separators=(",", ":"), default=str).encode()
        ).hexdigest()
        row = AuditLog(
            tenant_id=event.tenant_id,
            event_id=event.id,
            occurred_at=event.time,
            actor_type=event.actor_type,
            actor_id=event.actor_id,
            action=event.action,
            entity_type=event.entity_type,
            entity_id=event.entity_id,
            outcome=event.outcome,
            source_service=event.source,
            correlation_id=event.correlation_id,
            metadata_json=event.data,
            previous_hash=previous_hash,
            record_hash=record_hash,
        )
        self._session.add(row)
        self._session.add(
            ActivityEvent(
                tenant_id=event.tenant_id,
                user_id=UUID(event.actor_id) if event.actor_type == "user" else None,
                category=event.type,
                message=f"{event.action} {event.outcome}",
                related_entity_type=event.entity_type,
                related_entity_id=event.entity_id,
                occurred_at=event.time,
                metadata_json={"event_id": str(event.id)},
            )
        )
        await self._session.flush()
        return row

    async def search(
        self,
        tenant_id: UUID,
        *,
        start: datetime | None,
        end: datetime | None,
        actor_id: str | None,
        action: str | None,
        entity_type: str | None,
        entity_id: str | None,
        outcome: str | None,
        correlation_id: UUID | None,
        limit: int,
    ) -> list[AuditLog]:
        statement: Select[tuple[AuditLog]] = select(AuditLog).where(AuditLog.tenant_id == tenant_id)
        for condition in (
            AuditLog.occurred_at >= start if start else None,
            AuditLog.occurred_at <= end if end else None,
            AuditLog.actor_id == actor_id if actor_id else None,
            AuditLog.action == action if action else None,
            AuditLog.entity_type == entity_type if entity_type else None,
            AuditLog.entity_id == entity_id if entity_id else None,
            AuditLog.outcome == outcome if outcome else None,
            AuditLog.correlation_id == correlation_id if correlation_id else None,
        ):
            if condition is not None:
                statement = statement.where(condition)
        return list(
            await self._session.scalars(
                statement.order_by(AuditLog.occurred_at.desc()).limit(limit)
            )
        )
