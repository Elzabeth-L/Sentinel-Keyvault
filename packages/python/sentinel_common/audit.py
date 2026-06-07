import logging
from datetime import UTC, datetime, timedelta
from typing import Protocol

import httpx
from sqlalchemy import JSON, DateTime, Index, Integer, String, Text, Uuid, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Mapped, mapped_column

from sentinel_common.config import Settings
from sentinel_common.db import Base
from sentinel_common.events import AuditEvent
from sentinel_common.models import UUIDPrimaryKeyMixin

logger = logging.getLogger(__name__)


class AuditPublisher(Protocol):
    async def publish(self, event: AuditEvent) -> None: ...


class HttpAuditPublisher:
    """Internal transport for MVP; replace with Service Bus outbox relay in production."""

    def __init__(self, settings: Settings) -> None:
        self._url = f"{str(settings.audit_service_url).rstrip('/')}/api/v1/internal/events"
        self._token = settings.internal_api_token

    async def publish(self, event: AuditEvent) -> None:
        headers = {"X-Internal-Token": self._token} if self._token else {}
        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.post(
                self._url, json=event.model_dump(mode="json"), headers=headers
            )
            response.raise_for_status()


class LoggingAuditPublisher:
    async def publish(self, event: AuditEvent) -> None:
        logger.info("audit_event", extra={"event": event.model_dump(mode="json")})


class OutboxRecord(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "outbox"
    __table_args__ = (
        Index("ix_outbox_pending", "status", "available_at"),
        {"schema": "platform"},
    )

    tenant_id: Mapped[object] = mapped_column(Uuid, nullable=False)
    destination: Mapped[str] = mapped_column(String(128), nullable=False)
    event_type: Mapped[str] = mapped_column(String(255), nullable=False)
    payload: Mapped[dict[str, object]] = mapped_column(JSON, nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="pending")
    attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    available_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(UTC)
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(UTC)
    )
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_error: Mapped[str | None] = mapped_column(Text)


async def enqueue_audit(session: AsyncSession, event: AuditEvent) -> None:
    session.add(
        OutboxRecord(
            tenant_id=event.tenant_id,
            destination="audit",
            event_type=event.type,
            payload=event.model_dump(mode="json"),
        )
    )


async def claim_outbox(session: AsyncSession) -> OutboxRecord | None:
    now = datetime.now(UTC)
    record = await session.scalar(
        select(OutboxRecord)
        .where(
            or_(
                OutboxRecord.status == "pending",
                OutboxRecord.status == "publishing",
            ),
            OutboxRecord.available_at <= now,
        )
        .order_by(OutboxRecord.created_at)
        .with_for_update(skip_locked=True)
        .limit(1)
    )
    if record:
        record.status = "publishing"
        record.attempts += 1
        record.available_at = now + timedelta(minutes=5)
    return record
