from urllib.parse import urlencode

import httpx
from fastapi import HTTPException

from sentinel_common.config import Settings

LOGIN_SCOPES = ("openid", "profile", "email", "offline_access")
ARM_SCOPES = ("https://management.azure.com/user_impersonation",)


class MicrosoftOAuthService:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    def _client_id(self) -> str:
        if not self._settings.microsoft_client_id:
            raise RuntimeError("SENTINEL_MICROSOFT_CLIENT_ID is required")
        return self._settings.microsoft_client_id

    def _client_secret(self) -> str:
        if not self._settings.microsoft_client_secret:
            raise RuntimeError("SENTINEL_MICROSOFT_CLIENT_SECRET is required")
        return self._settings.microsoft_client_secret

    def authority(self, tenant_id: str | None) -> str:
        tenant = tenant_id or "common"
        return f"{str(self._settings.entra_authority_host).rstrip('/')}/{tenant}"

    def scopes(self) -> tuple[str, ...]:
        return (*LOGIN_SCOPES, *ARM_SCOPES)

    def authorization_url(self, state: str, challenge: str, tenant_id: str | None) -> str:
        query = urlencode(
            {
                "client_id": self._client_id(),
                "response_type": "code",
                "redirect_uri": self._settings.microsoft_redirect_uri,
                "response_mode": "query",
                "scope": " ".join(self.scopes()),
                "state": state,
                "code_challenge": challenge,
                "code_challenge_method": "S256",
                "prompt": "select_account",
            }
        )
        return f"{self.authority(tenant_id)}/oauth2/v2.0/authorize?{query}"

    async def exchange_code(
        self, code: str, verifier: str, tenant_id: str | None
    ) -> dict[str, object]:
        return await self._token_request(
            tenant_id,
            {
                "client_id": self._client_id(),
                "client_secret": self._client_secret(),
                "grant_type": "authorization_code",
                "code": code,
                "redirect_uri": self._settings.microsoft_redirect_uri,
                "code_verifier": verifier,
                "scope": " ".join(self.scopes()),
            },
        )

    async def refresh(self, refresh_token: str, tenant_id: str) -> dict[str, object]:
        return await self._token_request(
            tenant_id,
            {
                "client_id": self._client_id(),
                "client_secret": self._client_secret(),
                "grant_type": "refresh_token",
                "refresh_token": refresh_token,
                "scope": " ".join(self.scopes()),
            },
        )

    async def _token_request(
        self, tenant_id: str | None, data: dict[str, str]
    ) -> dict[str, object]:
        url = f"{self.authority(tenant_id)}/oauth2/v2.0/token"
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(url, data=data)
        if response.status_code >= 400:
            detail = response.json()
            raise HTTPException(status_code=401, detail=detail)
        payload: dict[str, object] = response.json()
        return payload
