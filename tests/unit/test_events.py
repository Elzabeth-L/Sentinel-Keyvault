from uuid import uuid4

from sentinel_common.events import AuditEvent


def test_audit_event_has_cloudevents_envelope() -> None:
    event = AuditEvent(
        source="test",
        type="test.created.v1",
        subject="test/1",
        tenant_id=uuid4(),
        correlation_id=uuid4(),
        data={},
        actor_type="user",
        actor_id=str(uuid4()),
        action="test.create",
        entity_type="test",
        entity_id="1",
        outcome="created",
    )
    assert event.specversion == "1.0"
    assert event.datacontenttype == "application/json"
