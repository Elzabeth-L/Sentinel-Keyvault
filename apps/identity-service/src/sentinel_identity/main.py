import base64
import hashlib
import logging
import secrets
from contextlib import asynccontextmanager
from uuid import UUID

from fastapi import Depends, FastAPI, Header, HTTPException, Query, Request, Response
from fastapi.responses import RedirectResponse

from sentinel_common.audit import enqueue_audit
from sentinel_common.auth import EntraTokenValidator
from sentinel_common.config import get_settings
from sentinel_common.db import create_engine, create_session_factory
from sentinel_common.events import AuditEvent
from sentinel_common.http import create_app
from sentinel_identity.account import refresh_authority
from sentinel_identity.bootstrap import bootstrap_identity
from sentinel_identity.dependencies import build_dependencies
from sentinel_identity.microsoft import MicrosoftOAuthService
from sentinel_identity.repository import IdentityRepository
from sentinel_identity.schemas import (
    AzureAccessTokenResponse,
    LoginResponse,
    PermissionResponse,
    ProfileResponse,
    RoleResponse,
)
from sentinel_identity.service import IdentityService, ResolvedIdentity
from sentinel_identity.session import SessionClaims, SessionCodec, TokenCipher
from sentinel_identity.storage import LoginBlobRecorder

settings = get_settings().model_copy(update={"service_name": "identity-service"})
logger = logging.getLogger(__name__)
engine = create_engine(settings)
session_factory = create_session_factory(engine)
validator = EntraTokenValidator(settings)
session_codec = SessionCodec(settings)
token_cipher = TokenCipher(settings)
oauth = MicrosoftOAuthService(settings)
login_blob_recorder = (
    LoginBlobRecorder(
        str(settings.login_blob_account_url),
        settings.login_blob_container_name,
    )
    if settings.login_blob_account_url
    else None
)
get_session, get_identity = build_dependencies(
    validator,
    session_codec,
    settings.session_cookie_name,
    session_factory,
)


@asynccontextmanager
async def lifespan(_: FastAPI):
    async with session_factory() as session:
        async with session.begin():
            await bootstrap_identity(session, settings)
    yield
    if login_blob_recorder is not None:
        await login_blob_recorder.close()
    await engine.dispose()


app = create_app(settings, engine)
app.router.lifespan_context = lifespan


def _oauth_cookie(response: Response, name: str, value: str) -> None:
    response.set_cookie(
        name,
        value,
        max_age=600,
        httponly=True,
        secure=settings.session_cookie_secure,
        samesite="lax",
        path="/",
    )


@app.get("/auth/login", response_model=LoginResponse, tags=["authentication"])
@app.get("/api/v1/auth/login", response_model=LoginResponse, tags=["authentication"])
async def login(response: Response, tenant: UUID | None = Query(None)) -> LoginResponse:
    state = secrets.token_urlsafe(32)
    verifier = secrets.token_urlsafe(64)
    challenge = (
        base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).rstrip(b"=").decode()
    )
    _oauth_cookie(response, "sentinel_oauth_state", state)
    _oauth_cookie(response, "sentinel_pkce_verifier", verifier)
    if tenant is not None:
        _oauth_cookie(response, "sentinel_oauth_tenant", str(tenant))
    else:
        response.delete_cookie("sentinel_oauth_tenant", path="/")
    return LoginResponse(
        authorization_url=oauth.authorization_url(state, challenge, str(tenant) if tenant else None)
    )


@app.get("/auth/callback", include_in_schema=False)
@app.get("/api/v1/auth/callback", include_in_schema=False)
async def callback(
    request: Request,
    code: str = Query(...),
    state: str = Query(...),
) -> RedirectResponse:
    expected_state = request.cookies.get("sentinel_oauth_state")
    verifier = request.cookies.get("sentinel_pkce_verifier")
    requested_tenant = request.cookies.get("sentinel_oauth_tenant")
    if not expected_state or not secrets.compare_digest(expected_state, state) or not verifier:
        raise HTTPException(status_code=401, detail="Invalid OAuth state")
    tokens = await oauth.exchange_code(code, verifier, requested_tenant)
    id_token = tokens.get("id_token")
    access_token = tokens.get("access_token")
    refresh_token = tokens.get("refresh_token")
    if not all(isinstance(item, str) and item for item in (id_token, access_token, refresh_token)):
        raise HTTPException(status_code=401, detail="Microsoft did not return required tokens")
    principal = await validator.validate(
        str(id_token),
        audience=settings.microsoft_client_id,
    )
    if requested_tenant and str(principal.entra_tenant_id) != requested_tenant:
        raise HTTPException(status_code=401, detail="Authenticated tenant does not match request")
    async with session_factory() as session:
        async with session.begin():
            identity = await IdentityService(session).onboard_oauth_user(
                principal,
                None,
                token_cipher.encrypt(str(refresh_token)),
                oauth.scopes(),
                refresh_authority(principal.entra_tenant_id, requested_tenant),
            )
            await enqueue_audit(
                session,
                AuditEvent(
                    source="identity-service",
                    type="identity.user-synchronized.v1",
                    subject=f"user/{identity.user.id}",
                    tenant_id=identity.tenant.id,
                    correlation_id=request.state.correlation_id,
                    data={"authentication": "authorization_code_pkce"},
                    actor_type="user",
                    actor_id=str(identity.user.id),
                    action="identity.login",
                    entity_type="user",
                    entity_id=str(identity.user.id),
                    outcome="succeeded",
                ),
            )
    if login_blob_recorder is not None:
        try:
            blob_name = await login_blob_recorder.record_login(
                identity,
                request.state.correlation_id,
            )
            logger.info(
                "login_blob_written",
                extra={
                    "blob_name": blob_name,
                    "tenant_id": str(identity.tenant.id),
                    "user_id": str(identity.user.id),
                    "correlation_id": request.state.correlation_id,
                },
            )
        except Exception:
            logger.exception(
                "login_blob_write_failed",
                extra={
                    "tenant_id": str(identity.tenant.id),
                    "user_id": str(identity.user.id),
                    "correlation_id": request.state.correlation_id,
                },
            )
    session_token = session_codec.encode(
        SessionClaims(
            user_id=identity.user.id,
            tenant_id=identity.tenant.id,
            entra_tenant_id=identity.tenant.entra_tenant_id,
            entra_object_id=identity.user.entra_object_id,
        )
    )
    response = RedirectResponse(url=f"{settings.frontend_url.rstrip('/')}/", status_code=302)
    response.set_cookie(
        settings.session_cookie_name,
        session_token,
        max_age=settings.session_ttl_seconds,
        httponly=True,
        secure=settings.session_cookie_secure,
        samesite="lax",
        domain=settings.session_cookie_domain,
        path="/",
    )
    for cookie in (
        "sentinel_oauth_state",
        "sentinel_pkce_verifier",
        "sentinel_oauth_tenant",
    ):
        response.delete_cookie(cookie, path="/")
    return response


@app.post("/auth/logout", tags=["authentication"])
@app.post("/api/v1/auth/logout", tags=["authentication"])
async def logout(response: Response) -> dict[str, str]:
    response.delete_cookie(
        settings.session_cookie_name,
        domain=settings.session_cookie_domain,
        path="/",
    )
    return {"status": "ok"}


@app.post(
    "/api/v1/internal/azure-token/{tenant_id}/{user_id}",
    response_model=AzureAccessTokenResponse,
    include_in_schema=False,
)
async def delegated_azure_token(
    tenant_id: UUID,
    user_id: UUID,
    x_internal_token: str | None = Header(None),
) -> AzureAccessTokenResponse:
    if not settings.internal_api_token or not secrets.compare_digest(
        x_internal_token or "", settings.internal_api_token
    ):
        raise HTTPException(status_code=401, detail="Invalid internal credential")
    async with session_factory() as session:
        async with session.begin():
            repository = IdentityRepository(session)
            tenant = await repository.get_tenant_by_id(tenant_id)
            user = await repository.get_user_by_id(tenant_id, user_id)
            connection = await repository.get_oauth_connection(tenant_id, user_id)
            if tenant is None or user is None or not user.is_active or connection is None:
                raise HTTPException(
                    status_code=409,
                    detail="User has no active delegated Microsoft OAuth connection",
                )
            tokens = await oauth.refresh(
                token_cipher.decrypt(connection.encrypted_refresh_token),
                connection.token_authority,
            )
            access_token = tokens.get("access_token")
            if not isinstance(access_token, str) or not access_token:
                raise HTTPException(status_code=502, detail="Microsoft token refresh failed")
            rotated_refresh_token = tokens.get("refresh_token")
            if isinstance(rotated_refresh_token, str) and rotated_refresh_token:
                await repository.upsert_oauth_connection(
                    tenant_id,
                    connection.user_id,
                    token_cipher.encrypt(rotated_refresh_token),
                    oauth.scopes(),
                    connection.token_authority,
                )
            expires_in = int(tokens.get("expires_in", 3600))
            return AzureAccessTokenResponse(
                access_token=access_token,
                expires_in=expires_in,
            )


@app.get("/auth/me", response_model=ProfileResponse, tags=["identity"])
@app.get("/api/v1/auth/me", response_model=ProfileResponse, tags=["identity"])
@app.get("/auth/profile", response_model=ProfileResponse, tags=["identity"])
@app.get("/api/v1/auth/profile", response_model=ProfileResponse, tags=["identity"])
async def profile(
    request: Request,
    identity: ResolvedIdentity = Depends(get_identity),
) -> ProfileResponse:
    async with session_factory() as session:
        async with session.begin():
            await enqueue_audit(
                session,
                AuditEvent(
                    source="identity-service",
                    type="identity.user-synchronized.v1",
                    subject=f"user/{identity.user.id}",
                    tenant_id=identity.tenant.id,
                    correlation_id=request.state.correlation_id,
                    data={"entra_object_id": str(identity.user.entra_object_id)},
                    actor_type="user",
                    actor_id=str(identity.user.id),
                    action="identity.profile.read",
                    entity_type="user",
                    entity_id=str(identity.user.id),
                    outcome="succeeded",
                ),
            )
    return ProfileResponse(
        user_id=identity.user.id,
        tenant_id=identity.tenant.id,
        entra_tenant_id=identity.tenant.entra_tenant_id,
        entra_object_id=identity.user.entra_object_id,
        display_name=identity.user.display_name,
        principal_name=identity.user.principal_name,
        roles=sorted(role.name for role in identity.roles),
        permissions=sorted(permission.name for permission in identity.permissions),
    )


@app.get("/api/v1/auth/permissions", response_model=list[PermissionResponse], tags=["identity"])
async def permissions(
    identity: ResolvedIdentity = Depends(get_identity),
) -> list[PermissionResponse]:
    if "identity.roles.read" not in {item.name for item in identity.permissions}:
        return [PermissionResponse.model_validate(item) for item in identity.permissions]
    async with session_factory() as session:
        return [
            PermissionResponse.model_validate(item)
            for item in await IdentityService(session).list_permissions()
        ]


@app.get("/api/v1/auth/roles", response_model=list[RoleResponse], tags=["identity"])
async def roles(identity: ResolvedIdentity = Depends(get_identity)) -> list[RoleResponse]:
    if "identity.roles.read" not in {item.name for item in identity.permissions}:
        raise HTTPException(status_code=403, detail="identity.roles.read is required")
    async with session_factory() as session:
        rows = await IdentityService(session).list_roles(identity.tenant.id)
    return [
        RoleResponse(
            id=role.id,
            name=role.name,
            description=role.description,
            permissions=permissions,
        )
        for role, permissions in rows
    ]
