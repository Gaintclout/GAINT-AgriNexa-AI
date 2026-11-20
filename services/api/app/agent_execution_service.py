"""Internal Intake/Profile execution with mandatory persistent auditing.

Not exposed through HTTP. Database schema readiness and deployment
approval are separate requirements.
"""

from sqlalchemy.orm import Session

from .agent_audit_sink import make_database_audit_sink
from .agent_audited_pipeline import run_audited_pipeline
from .agent_pipeline import PipelineRequest, PipelineResult
from .database import session_factory
from .security import Principal


def execute_audited_intake_profile(
    db: Session,
    principal: Principal,
    request: PipelineRequest,
) -> PipelineResult:
    """Return a profile only after its audit event is persisted."""

    audit_sink = make_database_audit_sink(session_factory)

    return run_audited_pipeline(
        db,
        principal,
        request,
        audit_sink,
    )
