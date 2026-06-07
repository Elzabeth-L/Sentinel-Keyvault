from contextvars import ContextVar, Token
from dataclasses import dataclass
from uuid import UUID


@dataclass(frozen=True, slots=True)
class ActorContext:
    tenant_id: UUID
    entra_tenant_id: UUID
    actor_id: UUID
    entra_object_id: UUID
    display_name: str
    principal_name: str | None
    permissions: frozenset[str]
    correlation_id: UUID


_actor: ContextVar[ActorContext | None] = ContextVar("sentinel_actor", default=None)


def set_actor(actor: ActorContext) -> Token[ActorContext | None]:
    return _actor.set(actor)


def reset_actor(token: Token[ActorContext | None]) -> None:
    _actor.reset(token)


def current_actor() -> ActorContext:
    actor = _actor.get()
    if actor is None:
        raise RuntimeError("Actor context is not available")
    return actor
