import json
from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest
from sentinel_identity.storage import LoginBlobRecorder


@pytest.mark.asyncio
async def test_login_blob_recorder_writes_non_sensitive_json() -> None:
    container = AsyncMock()
    identity = SimpleNamespace(
        tenant=SimpleNamespace(
            id=uuid4(),
            entra_tenant_id=uuid4(),
            account_type="organization",
        ),
        user=SimpleNamespace(
            id=uuid4(),
            entra_object_id=uuid4(),
        ),
    )
    recorder = LoginBlobRecorder(
        "https://unused.blob.core.windows.net",
        "sentinel-login-events",
        container_client=container,
    )

    blob_name = await recorder.record_login(identity, "correlation-123")

    container.create_container.assert_awaited_once()
    upload = container.upload_blob.await_args.kwargs
    document = json.loads(upload["data"])
    assert blob_name.startswith("login-events/")
    assert document["event_type"] == "identity.login.succeeded"
    assert document["correlation_id"] == "correlation-123"
    assert "token" not in upload["data"]
    assert "email" not in upload["data"]
