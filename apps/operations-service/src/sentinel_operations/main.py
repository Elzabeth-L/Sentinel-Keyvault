from fastapi import Depends, Header, HTTPException, status
from sqlalchemy import select

from sentinel_common.audit import enqueue_audit
from sentinel_common.auth import (
    IdentityProfileClient,
    actor_dependency,
    permission_dependency,
)
from sentinel_common.config import get_settings
from sentinel_common.context import ActorContext
from sentinel_common.db import UnitOfWork, create_engine, create_session_factory
from sentinel_common.events import AuditEvent
from sentinel_common.http import create_app
from sentinel_operations.domain import ACTION_CATALOG
from sentinel_operations.models import Operation
from sentinel_operations.schemas import ActionResponse, OperationCreate, OperationResponse

settings = get_settings().model_copy(update={"service_name": "operations-service"})
engine = create_engine(settings)
session_factory = create_session_factory(engine)
get_actor = actor_dependency(IdentityProfileClient(settings))
create_operation = permission_dependency(get_actor, "operations.create")
execute_operation = permission_dependency(get_actor, "operations.execute")
app = create_app(settings, engine)


@app.get(
    "/api/v1/operations/action-catalog", response_model=list[ActionResponse], tags=["operations"]
)
async def action_catalog(actor: ActorContext = Depends(get_actor)) -> list[ActionResponse]:
    return [
        ActionResponse(
            action_type=item.action_type,
            display_name=item.display_name,
            required_permission=item.required_permission,
            azure_permissions=list(item.azure_permissions),
            destructive=item.destructive,
            enabled=item.enabled,
            parameter_schema=item.parameter_schema,
        )
        for item in ACTION_CATALOG
    ]


@app.post(
    "/api/v1/operations",
    response_model=OperationResponse,
    status_code=status.HTTP_201_CREATED,
    tags=["operations"],
)
async def create(
    request: OperationCreate,
    idempotency_key: str = Header(min_length=8, max_length=255, alias="Idempotency-Key"),
    actor: ActorContext = Depends(create_operation),
) -> OperationResponse:
    definition = next(
        (item for item in ACTION_CATALOG if item.action_type == request.action_type), None
    )
    if definition is None:
        raise HTTPException(status_code=422, detail="Unsupported operation action")
    async with UnitOfWork(session_factory, actor.tenant_id, actor.actor_id) as uow:
        existing = await uow.session.scalar(
            select(Operation).where(
                Operation.tenant_id == actor.tenant_id,
                Operation.idempotency_key == idempotency_key,
            )
        )
        if existing:
            return OperationResponse.model_validate(existing)
        operation = Operation(
            tenant_id=actor.tenant_id,
            assessment_id=request.assessment_id,
            assessment_input_sha256=request.assessment_input_hash,
            action_type=request.action_type,
            target_resource_id=request.target_resource_id,
            requested_by=actor.actor_id,
            reason=request.reason,
            status="draft",
            idempotency_key=idempotency_key,
            policy_snapshot={"executor_enabled": definition.enabled},
            parameters_snapshot=request.parameters,
            correlation_id=actor.correlation_id,
        )
        uow.session.add(operation)
        await uow.session.flush()
        await enqueue_audit(
            uow.session,
            AuditEvent(
                source="operations-service",
                type="operations.created.v1",
                subject=f"operation/{operation.id}",
                tenant_id=actor.tenant_id,
                correlation_id=actor.correlation_id,
                data={"action_type": request.action_type, "status": operation.status},
                actor_type="user",
                actor_id=str(actor.actor_id),
                action="operation.create",
                entity_type="operation",
                entity_id=str(operation.id),
                outcome="created",
            ),
        )
        return OperationResponse.model_validate(operation)


@app.post("/api/v1/operations/{operation_id}/execute", status_code=409, tags=["operations"])
async def execute(
    operation_id: str,
    actor: ActorContext = Depends(execute_operation),
) -> None:
    raise HTTPException(
        status_code=409,
        detail=(
            "Execution is disabled until reviewed Azure executors "
            "and approval validation are deployed"
        ),
    )
