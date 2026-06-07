import time
from dataclasses import dataclass
from typing import Any
from uuid import UUID

import jwt
from cryptography.fernet import Fernet, InvalidToken
from fastapi import HTTPException, status

from sentinel_common.config import Settings


@dataclass(frozen=True, slots=True)
class SessionClaims:
    user_id: UUID
    tenant_id: UUID
    entra_tenant_id: UUID
    entra_object_id: UUID


class SessionCodec:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    def _signing_key(self) -> str:
        if not self._settings.session_signing_key:
            raise RuntimeError("SENTINEL_SESSION_SIGNING_KEY is required")
        return self._settings.session_signing_key

    def encode(self, claims: SessionClaims) -> str:
        now = int(time.time())
        payload = {
            "sub": str(claims.user_id),
            "tenant_id": str(claims.tenant_id),
            "tid": str(claims.entra_tenant_id),
            "oid": str(claims.entra_object_id),
            "iat": now,
            "nbf": now,
            "exp": now + self._settings.session_ttl_seconds,
            "iss": "sentinel-identity",
            "aud": "sentinel-services",
        }
        return jwt.encode(payload, self._signing_key(), algorithm="HS256")

    def decode(self, token: str) -> SessionClaims:
        try:
            payload: dict[str, Any] = jwt.decode(
                token,
                self._signing_key(),
                algorithms=["HS256"],
                issuer="sentinel-identity",
                audience="sentinel-services",
                options={"require": ["sub", "tenant_id", "tid", "oid", "exp", "iat", "nbf"]},
            )
            return SessionClaims(
                user_id=UUID(payload["sub"]),
                tenant_id=UUID(payload["tenant_id"]),
                entra_tenant_id=UUID(payload["tid"]),
                entra_object_id=UUID(payload["oid"]),
            )
        except (jwt.PyJWTError, KeyError, ValueError) as exc:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid or expired Sentinel session",
            ) from exc


class TokenCipher:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    def _fernet(self) -> Fernet:
        if not self._settings.token_encryption_key:
            raise RuntimeError("SENTINEL_TOKEN_ENCRYPTION_KEY is required")
        return Fernet(self._settings.token_encryption_key.encode())

    def encrypt(self, value: str) -> str:
        return self._fernet().encrypt(value.encode()).decode()

    def decrypt(self, value: str) -> str:
        try:
            return self._fernet().decrypt(value.encode()).decode()
        except InvalidToken as exc:
            raise RuntimeError("Stored Microsoft refresh token cannot be decrypted") from exc
