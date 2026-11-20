"""Fail-closed persistent auditing for human-review agent operations."""

from uuid import uuid4

from .agent_audit import build_review_audit_event
from .agent_audit_sink import make_database_audit_sink
from .database import session_factory
from .escalation_agent import (
    EscalationRequest,
    EscalationResult,
    evaluate_escalation,
)
from .learning_agent import LearningRequest, LearningResult, evaluate_learning
from .security import Principal


def execute_audited_escalation_review(
    principal: Principal,
    request: EscalationRequest,
) -> EscalationResult:
    correlation_id = str(uuid4())
    result = evaluate_escalation(request)
    sink = make_database_audit_sink(session_factory)
    sink(build_review_audit_event(
        principal,
        request.case_reference,
        "ESCALATION_REVIEW",
        correlation_id=correlation_id,
    ))
    return result.model_copy(update={"correlation_id": correlation_id})


def execute_audited_learning_review(
    principal: Principal,
    request: LearningRequest,
) -> LearningResult:
    correlation_id = str(uuid4())
    result = evaluate_learning(request)
    sink = make_database_audit_sink(session_factory)
    sink(build_review_audit_event(
        principal,
        request.review_reference,
        "LEARNING_REVIEW",
        correlation_id=correlation_id,
    ))
    return result.model_copy(update={"correlation_id": correlation_id})
