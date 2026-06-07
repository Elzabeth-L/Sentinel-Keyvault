import asyncio
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any, cast
from uuid import UUID

import httpx
import jwt
from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jwt import PyJWKClient

from sentinel_common.config import Settings
from sentinel_common.context import ActorContext


@dataclass(frozen=True, slots=True)
class TokenPrincipal:
    entra_tenant_id: UUID
    entra_object_id: UUID
    display_name: str
    principal_name: str | None
    scopes: frozenset[str]
    roles: frozenset[str]
    claims: dict[str, Any]


class EntraTokenValidator:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        host = str(settings.entra_authority_host).rstrip("/")
        self._jwks = PyJWKClient(f"{host}/common/discovery/v2.0/keys", cache_keys=True)

    async def validate(self, token: str, audience: str | None = None) -> TokenPrincipal:
        try:
            expected_audience = audience or self._settings.entra_audience
            if not expected_audience:
                raise RuntimeError("Microsoft token audience is not configured")
            header = jwt.get_unverified_header(token)
            claims = jwt.decode(token, options={"verify_signature": False})
            tenant_id = UUID(str(claims["tid"]))
            if (
                self._settings.allowed_tenants
                and str(tenant_id) not in self._settings.allowed_tenants
            ):
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN, detail="Tenant is not allowed"
                )

            signing_key = await asyncio.to_thread(self._jwks.get_signing_key, header["kid"])
            issuer = f"{str(self._settings.entra_authority_host).rstrip('/')}/{tenant_id}/v2.0"
            verified = jwt.decode(
                token,
                signing_key.key,
                algorithms=["RS256"],
                audience=expected_audience,
                issuer=issuer,
                leeway=60,
                options={"require": ["exp", "iat", "nbf", "tid", "oid"]},
            )
            return TokenPrincipal(
                entra_tenant_id=tenant_id,
                entra_object_id=UUID(str(verified["oid"])),
                display_name=str(
                    verified.get("name") or verified.get("preferred_username") or "User"
                ),
                principal_name=verified.get("preferred_username"),
                scopes=frozenset(str(verified.get("scp", "")).split()),
                roles=frozenset(verified.get("roles", [])),
                claims=verified,
            )
        except HTTPException:
            raise
        except (KeyError, ValueError, jwt.PyJWTError) as exc:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid Microsoft Entra access token",
                headers={"WWW-Authenticate": "Bearer"},
            ) from exc


class IdentityProfileClient:
    def __init__(self, settings: Settings) -> None:
        self._url = f"{str(settings.identity_service_url).rstrip('/')}/api/v1/auth/profile"

    async def resolve(
        self,
        correlation_id: UUID,
        cookie_header: str | None,
        authorization: str | None,
    ) -> dict[str, Any]:
        headers = {"X-Correlation-ID": str(correlation_id)}
        if cookie_header:
            headers["Cookie"] = cookie_header
        if authorization:
            headers["Authorization"] = authorization
        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.get(self._url, headers=headers)
        if response.status_code == 401:
            raise HTTPException(status_code=401, detail="Authentication failed")
        if response.status_code == 403:
            raise HTTPException(status_code=403, detail="Tenant or user is not authorized")
        response.raise_for_status()
        return cast(dict[str, Any], response.json())


bearer_scheme = HTTPBearer(auto_error=False)


def actor_dependency(
    client: IdentityProfileClient,
) -> Callable[..., Awaitable[ActorContext]]:
    async def get_actor(
        request: Request,
        credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    ) -> ActorContext:
        authorization = (
            f"{credentials.scheme} {credentials.credentials}" if credentials is not None else None
        )
        profile = await client.resolve(
            request.state.correlation_id,
            request.headers.get("cookie"),
            authorization,
        )
        actor = ActorContext(
            tenant_id=UUID(profile["tenant_id"]),
            entra_tenant_id=UUID(profile["entra_tenant_id"]),
            actor_id=UUID(profile["user_id"]),
            entra_object_id=UUID(profile["entra_object_id"]),
            display_name=profile["display_name"],
            principal_name=profile.get("principal_name"),
            permissions=frozenset(profile["permissions"]),
            correlation_id=request.state.correlation_id,
        )
        request.state.actor = actor
        return actor

    return get_actor


def permission_dependency(
    get_actor: Callable[..., Awaitable[ActorContext]],
    permission: str,
) -> Callable[..., Awaitable[ActorContext]]:
    async def require(actor: ActorContext = Depends(get_actor)) -> ActorContext:
        if permission not in actor.permissions:
            raise HTTPException(status_code=403, detail=f"Permission {permission} is required")
        return actor

    return require
