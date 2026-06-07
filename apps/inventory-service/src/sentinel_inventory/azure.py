from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Protocol
from uuid import UUID

import httpx
from azure.core.credentials import AccessToken
from azure.core.credentials_async import AsyncTokenCredential
from azure.identity.aio import CertificateCredential, DefaultAzureCredential
from azure.mgmt.resource.subscriptions.aio import SubscriptionClient
from azure.mgmt.resourcegraph.aio import ResourceGraphClient
from azure.mgmt.resourcegraph.models import QueryRequest, QueryRequestOptions

from sentinel_common.config import Settings

SUPPORTED_TYPES = (
    "microsoft.containerservice/managedclusters",
    "microsoft.keyvault/vaults",
    "microsoft.storage/storageaccounts",
    "microsoft.network/virtualnetworks",
    "microsoft.network/applicationgateways",
    "microsoft.network/loadbalancers",
    "microsoft.web/sites",
    "microsoft.managedidentity/userassignedidentities",
    "microsoft.resources/subscriptions/resourcegroups",
)


@dataclass(frozen=True, slots=True)
class AzureSubscription:
    subscription_id: UUID
    display_name: str
    state: str


class AzureInventoryProvider(Protocol):
    async def list_subscriptions(self) -> list[AzureSubscription]: ...
    async def query_resources(self, subscription_ids: list[UUID]) -> list[dict[str, object]]: ...


class IdentityDelegatedCredential:
    def __init__(self, settings: Settings, tenant_id: UUID, user_id: UUID) -> None:
        self._url = (
            f"{str(settings.identity_service_url).rstrip('/')}"
            f"/api/v1/internal/azure-token/{tenant_id}/{user_id}"
        )
        self._internal_token = settings.internal_api_token
        self._cached: AccessToken | None = None

    async def get_token(self, *scopes: str, **kwargs: object) -> AccessToken:
        del scopes, kwargs
        now = datetime.now(UTC).timestamp()
        if self._cached and self._cached.expires_on - now > 300:
            return self._cached
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                self._url,
                headers={"X-Internal-Token": self._internal_token or ""},
            )
        response.raise_for_status()
        payload = response.json()
        expires_in = int(payload.get("expires_in", 3600))
        self._cached = AccessToken(
            payload["access_token"],
            int((datetime.now(UTC) + timedelta(seconds=expires_in)).timestamp()),
        )
        return self._cached

    async def close(self) -> None:
        self._cached = None


class ResourceGraphInventoryProvider:
    def __init__(
        self,
        settings: Settings,
        customer_tenant_id: UUID | None = None,
        credential: AsyncTokenCredential | None = None,
    ) -> None:
        if credential is not None:
            self._credential = credential
        elif (
            settings.azure_tenant_id
            and settings.azure_client_id
            and settings.azure_client_certificate_path
        ):
            self._credential = CertificateCredential(
                tenant_id=str(customer_tenant_id or settings.azure_tenant_id),
                client_id=settings.azure_client_id,
                certificate_path=settings.azure_client_certificate_path,
            )
        else:
            self._credential = DefaultAzureCredential()

    async def list_subscriptions(self) -> list[AzureSubscription]:
        client = SubscriptionClient(self._credential)
        try:
            output: list[AzureSubscription] = []
            async for item in client.subscriptions.list():
                if item.subscription_id:
                    output.append(
                        AzureSubscription(
                            subscription_id=UUID(item.subscription_id),
                            display_name=item.display_name or item.subscription_id,
                            state=str(item.state or "Unknown"),
                        )
                    )
            return output
        finally:
            await client.close()

    async def query_resources(self, subscription_ids: list[UUID]) -> list[dict[str, object]]:
        quoted_types = ", ".join(f"'{item}'" for item in SUPPORTED_TYPES)
        query = f"""
            Resources
            | where tolower(type) in ({quoted_types})
            | project id, name, type, subscriptionId, resourceGroup, location,
                      kind, sku, tags, properties
        """
        client = ResourceGraphClient(self._credential)
        try:
            rows: list[dict[str, object]] = []
            skip_token: str | None = None
            while True:
                request = QueryRequest(
                    subscriptions=[str(item) for item in subscription_ids],
                    query=query,
                    options=QueryRequestOptions(
                        result_format="objectArray",
                        top=1000,
                        skip_token=skip_token,
                    ),
                )
                response = await client.resources(request)
                rows.extend(dict(item) for item in (response.data or []))
                skip_token = response.skip_token
                if not skip_token:
                    return rows
        finally:
            await client.close()
