from typing import Protocol

from azure.identity.aio import DefaultAzureCredential
from azure.keyvault.secrets.aio import SecretClient


class SecretProvider(Protocol):
    async def get_secret(self, name: str) -> str: ...


class KeyVaultSecretProvider:
    """Managed-identity Key Vault access for values that cannot be federated."""

    def __init__(self, vault_url: str, credential: DefaultAzureCredential | None = None) -> None:
        self._credential = credential or DefaultAzureCredential()
        self._client = SecretClient(vault_url=vault_url, credential=self._credential)

    async def get_secret(self, name: str) -> str:
        secret = await self._client.get_secret(name)
        if secret.value is None:
            raise ValueError(f"Key Vault secret {name!r} has no value")
        return secret.value

    async def close(self) -> None:
        await self._client.close()
        await self._credential.close()
