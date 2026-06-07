from uuid import uuid4

import pytest
from cryptography.fernet import Fernet
from fastapi import HTTPException
from sentinel_identity.account import (
    MICROSOFT_CONSUMER_TENANT_ID,
    identity_scope_key,
    refresh_authority,
)
from sentinel_identity.microsoft import MicrosoftOAuthService
from sentinel_identity.session import SessionClaims, SessionCodec, TokenCipher

from sentinel_common.config import Settings


def auth_settings() -> Settings:
    return Settings(
        entra_audience="api://sentinel",
        microsoft_client_id="00000000-0000-0000-0000-000000000001",
        microsoft_client_secret="test-only-value",  # noqa: S106
        session_signing_key="test-session-signing-key-with-sufficient-entropy-0123456789",
        token_encryption_key=Fernet.generate_key().decode(),
    )


def test_session_round_trip() -> None:
    codec = SessionCodec(auth_settings())
    claims = SessionClaims(
        user_id=uuid4(),
        tenant_id=uuid4(),
        entra_tenant_id=uuid4(),
        entra_object_id=uuid4(),
    )
    assert codec.decode(codec.encode(claims)) == claims


def test_session_rejects_invalid_signature() -> None:
    settings = auth_settings()
    token = SessionCodec(settings).encode(SessionClaims(uuid4(), uuid4(), uuid4(), uuid4()))
    other = settings.model_copy(
        update={"session_signing_key": "different-test-signing-key-with-32-bytes-minimum"}
    )
    with pytest.raises(HTTPException):
        SessionCodec(other).decode(token)


def test_refresh_token_encryption_round_trip() -> None:
    cipher = TokenCipher(auth_settings())
    encrypted = cipher.encrypt("refresh-token-value")
    assert encrypted != "refresh-token-value"
    assert cipher.decrypt(encrypted) == "refresh-token-value"


def test_authorization_url_uses_pkce_and_single_resource_scope() -> None:
    service = MicrosoftOAuthService(auth_settings())
    url = service.authorization_url("state", "challenge", "tenant-id")
    assert "code_challenge=challenge" in url
    assert "code_challenge_method=S256" in url
    assert "management.azure.com%2Fuser_impersonation" in url
    assert "graph.microsoft.com" not in url


def test_personal_accounts_receive_user_isolated_workspaces() -> None:
    first_user = uuid4()
    second_user = uuid4()
    assert identity_scope_key(MICROSOFT_CONSUMER_TENANT_ID, first_user) != identity_scope_key(
        MICROSOFT_CONSUMER_TENANT_ID, second_user
    )


def test_organization_accounts_share_their_tenant_workspace() -> None:
    tenant_id = uuid4()
    assert identity_scope_key(tenant_id, uuid4()) == identity_scope_key(tenant_id, uuid4())


def test_personal_refresh_uses_common_authority() -> None:
    assert refresh_authority(MICROSOFT_CONSUMER_TENANT_ID, None) == "common"
