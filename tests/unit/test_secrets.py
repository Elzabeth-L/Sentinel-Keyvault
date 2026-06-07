from unittest.mock import AsyncMock

import pytest

from sentinel_common.secrets import KeyVaultSecretProvider


@pytest.mark.asyncio
async def test_key_vault_provider_rejects_empty_secret() -> None:
    provider = object.__new__(KeyVaultSecretProvider)
    provider._client = AsyncMock()
    provider._client.get_secret.return_value.value = None
    with pytest.raises(ValueError):
        await provider.get_secret("empty")
