import asyncio
import logging
from datetime import UTC, datetime, timedelta

from sentinel_common.audit import HttpAuditPublisher, claim_outbox
from sentinel_common.config import get_settings
from sentinel_common.db import create_engine, create_session_factory
from sentinel_common.events import AuditEvent
from sentinel_common.http import configure_logging

logger = logging.getLogger(__name__)


async def run() -> None:
    settings = get_settings().model_copy(update={"service_name": "outbox-relay"})
    configure_logging(settings)
    engine = create_engine(settings)
    sessions = create_session_factory(engine)
    publisher = HttpAuditPublisher(settings)
    try:
        while True:
            async with sessions() as session:
                async with session.begin():
                    record = await claim_outbox(session)
                if record is None:
                    await asyncio.sleep(1)
                    continue
                try:
                    await publisher.publish(AuditEvent.model_validate(record.payload))
                    async with session.begin():
                        record.status = "published"
                        record.published_at = datetime.now(UTC)
                        record.last_error = None
                except Exception as exc:
                    logger.exception("outbox_publish_failed", extra={"outbox_id": str(record.id)})
                    async with session.begin():
                        record.status = "pending" if record.attempts < 20 else "dead"
                        record.available_at = datetime.now(UTC) + timedelta(
                            seconds=min(300, 2 ** min(record.attempts, 8))
                        )
                        record.last_error = str(exc)[:2000]
    finally:
        await engine.dispose()


if __name__ == "__main__":
    asyncio.run(run())
