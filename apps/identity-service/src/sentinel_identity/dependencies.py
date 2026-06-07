from collections.abc import AsyncIterator, Callable

from fastapi import Depends, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from sentinel_common.auth import EntraTokenValidator
from sentinel_common.context import ActorContext
from sentinel_identity.service import IdentityService, ResolvedIdentity
from sentinel_identity.session import SessionCodec

bearer = HTTPBearer(auto_error=False)


def build_dependencies(
    validator: EntraTokenValidator,
    session_codec: SessionCodec,
    session_cookie_name: str,
    session_factory: Callable[[], AsyncSession],
) -> tuple[Callable[..., AsyncIterator[AsyncSession]], Callable[..., ResolvedIdentity]]:
    async def get_session() -> AsyncIterator[AsyncSession]:
        async with session_factory() as session:
            async with session.begin():
                yield session

    async def get_identity(
        request: Request,
        credentials: HTTPAuthorizationCredentials | None = Depends(bearer),
        session: AsyncSession = Depends(get_session),
    ) -> ResolvedIdentity:
        service = IdentityService(session)
        session_token = request.cookies.get(session_cookie_name)
        if session_token:
            claims = session_codec.decode(session_token)
            identity = await service.resolve_session(claims.tenant_id, claims.user_id)
        elif credentials is not None:
            principal = await validator.validate(credentials.credentials)
            identity = await service.resolve_and_sync(principal)
        else:
            from fastapi import HTTPException

            raise HTTPException(status_code=401, detail="Not authenticated")
        request.state.actor = ActorContext(
            tenant_id=identity.tenant.id,
            entra_tenant_id=identity.tenant.entra_tenant_id,
            actor_id=identity.user.id,
            entra_object_id=identity.user.entra_object_id,
            display_name=identity.user.display_name,
            principal_name=identity.user.principal_name,
            permissions=frozenset(item.name for item in identity.permissions),
            correlation_id=request.state.correlation_id,
        )
        return identity

    return get_session, get_identity
