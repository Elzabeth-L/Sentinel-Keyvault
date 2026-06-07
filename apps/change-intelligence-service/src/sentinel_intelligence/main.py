import hashlib
import json

from fastapi import Depends, HTTPException, status
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
from sentinel_intelligence.models import ChangeAssessment
from sentinel_intelligence.schemas import AssessmentCreate, AssessmentResponse

settings = get_settings().model_copy(update={"service_name": "change-intelligence-service"})
engine = create_engine(settings)
session_factory = create_session_factory(engine)
get_actor = actor_dependency(IdentityProfileClient(settings))
create_analysis = permission_dependency(get_actor, "analysis.create")
read_analysis = permission_dependency(get_actor, "analysis.read")
app = create_app(settings, engine)


@app.post(
    "/api/v1/analysis/assessments",
    response_model=AssessmentResponse,
    status_code=status.HTTP_202_ACCEPTED,
    tags=["analysis"],
)
@app.post(
    "/api/v1/analysis/impact",
    response_model=AssessmentResponse,
    status_code=status.HTTP_202_ACCEPTED,
    tags=["analysis"],
)
@app.post(
    "/api/v1/analysis/risk",
    response_model=AssessmentResponse,
    status_code=status.HTTP_202_ACCEPTED,
    tags=["analysis"],
)
async def create_assessment(
    request: AssessmentCreate,
    actor: ActorContext = Depends(create_analysis),
) -> AssessmentResponse:
    canonical = {
        "action_type": request.action_type,
        "target_resource_id": str(request.target_resource_id),
        "parameters": request.parameters,
    }
    digest = (
        "sha256:"
        + hashlib.sha256(
            json.dumps(canonical, sort_keys=True, separators=(",", ":")).encode()
        ).hexdigest()
    )
    async with UnitOfWork(session_factory, actor.tenant_id, actor.actor_id) as uow:
        assessment = ChangeAssessment(
            tenant_id=actor.tenant_id,
            requested_by=actor.actor_id,
            target_resource_id=request.target_resource_id,
            action_type=request.action_type,
            parameters=request.parameters,
            status="draft",
            canonical_input=canonical,
            input_sha256=digest,
            correlation_id=actor.correlation_id,
        )
        uow.session.add(assessment)
        await uow.session.flush()
        await enqueue_audit(
            uow.session,
            AuditEvent(
                source="change-intelligence-service",
                type="intelligence.assessment-requested.v1",
                subject=f"assessment/{assessment.id}",
                tenant_id=actor.tenant_id,
                correlation_id=actor.correlation_id,
                data={"action_type": request.action_type, "input_sha256": digest},
                actor_type="user",
                actor_id=str(actor.actor_id),
                action="assessment.create",
                entity_type="assessment",
                entity_id=str(assessment.id),
                outcome="accepted",
            ),
        )
        return AssessmentResponse.model_validate(assessment)


@app.get(
    "/api/v1/analysis/assessments/{assessment_id}",
    response_model=AssessmentResponse,
    tags=["analysis"],
)
async def get_assessment(
    assessment_id: str,
    actor: ActorContext = Depends(read_analysis),
) -> AssessmentResponse:
    async with UnitOfWork(session_factory, actor.tenant_id, actor.actor_id) as uow:
        assessment = await uow.session.scalar(
            select(ChangeAssessment).where(
                ChangeAssessment.tenant_id == actor.tenant_id,
                ChangeAssessment.id == assessment_id,
            )
        )
        if assessment is None:
            raise HTTPException(status_code=404, detail="Assessment not found")
        return AssessmentResponse.model_validate(assessment)
