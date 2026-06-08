import asyncio
import json
from datetime import UTC, datetime
from uuid import uuid4

from azure.core.exceptions import ResourceExistsError
from azure.identity.aio import DefaultAzureCredential
from azure.storage.blob import ContentSettings
from azure.storage.blob.aio import BlobServiceClient, ContainerClient

from sentinel_identity.service import ResolvedIdentity


class LoginBlobRecorder:
    def __init__(
        self,
        account_url: str,
        container_name: str,
        credential: DefaultAzureCredential | None = None,
        container_client: ContainerClient | None = None,
    ) -> None:
        self._credential = credential
        self._owns_credential = credential is None
        self._service_client: BlobServiceClient | None = None
        if container_client is not None:
            self._container = container_client
        else:
            self._credential = credential or DefaultAzureCredential()
            self._service_client = BlobServiceClient(
                account_url=account_url,
                credential=self._credential,
            )
            self._container = self._service_client.get_container_client(container_name)
        self._container_ready = False
        self._container_lock = asyncio.Lock()

    async def record_login(
        self,
        identity: ResolvedIdentity,
        correlation_id: str,
    ) -> str:
        await self._ensure_container()
        occurred_at = datetime.now(UTC)
        blob_name = (
            f"login-events/{occurred_at:%Y/%m/%d}/"
            f"{occurred_at:%H%M%S}-{identity.user.id}-{uuid4()}.json"
        )
        document = {
            "schema_version": 1,
            "event_type": "identity.login.succeeded",
            "occurred_at": occurred_at.isoformat(),
            "correlation_id": correlation_id,
            "tenant": {
                "id": str(identity.tenant.id),
                "entra_tenant_id": str(identity.tenant.entra_tenant_id),
                "account_type": identity.tenant.account_type,
            },
            "user": {
                "id": str(identity.user.id),
                "entra_object_id": str(identity.user.entra_object_id),
            },
        }
        await self._container.upload_blob(
            name=blob_name,
            data=json.dumps(document, separators=(",", ":"), sort_keys=True),
            overwrite=False,
            content_settings=ContentSettings(content_type="application/json"),
        )
        return blob_name

    async def close(self) -> None:
        if self._service_client is not None:
            await self._service_client.close()
        if self._owns_credential and self._credential is not None:
            await self._credential.close()

    async def _ensure_container(self) -> None:
        if self._container_ready:
            return
        async with self._container_lock:
            if self._container_ready:
                return
            try:
                await self._container.create_container()
            except ResourceExistsError:
                pass
            self._container_ready = True
