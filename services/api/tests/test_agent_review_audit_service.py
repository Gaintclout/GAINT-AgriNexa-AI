from unittest.mock import Mock, patch

import pytest

from app.agent_audit_sink import AgentAuditStorageError
from app.agent_review_audit_service import (
    execute_audited_escalation_review,
    execute_audited_learning_review,
)
from app.escalation_agent import EscalationRequest, Evidence
from app.learning_agent import FeedbackItem, LearningRequest
from app.security import Principal, Role


def actor():
    return Principal(subject="reviewer-1", role=Role.admin)


def escalation_request():
    return EscalationRequest(
        case_reference="CASE-18",
        indicators=[Evidence(
            indicator="crop_damage",
            description="Verified length agricultural observation",
            source_type="field_observation",
        )],
    )


def learning_request():
    return LearningRequest(
        review_reference="REVIEW-18",
        feedback=[FeedbackItem(
            feedback_id="FB-18",
            agent_domain="crop_advisory",
            recommendation_reference="REC-18",
            outcome="incomplete",
            explanation="The recommendation needs further human review.",
        )],
    )


@pytest.mark.parametrize(
    ("execute", "request_factory", "operation", "subject"),
    [
        (execute_audited_escalation_review, escalation_request, "ESCALATION_REVIEW", "CASE-18"),
        (execute_audited_learning_review, learning_request, "LEARNING_REVIEW", "REVIEW-18"),
    ],
)
def test_review_commits_minimal_correlated_audit(execute, request_factory, operation, subject):
    sink = Mock()
    with patch(
        "app.agent_review_audit_service.make_database_audit_sink",
        return_value=sink,
    ):
        result = execute(actor(), request_factory())

    event = sink.call_args.args[0]
    assert result.correlation_id == event.correlation_id
    assert event.operation == operation
    assert event.subject_id == subject
    assert event.parcel_id is None
    assert event.outcome == "allowed"
    assert result.advisory_only is True


@pytest.mark.parametrize(
    ("execute", "request_factory"),
    [
        (execute_audited_escalation_review, escalation_request),
        (execute_audited_learning_review, learning_request),
    ],
)
def test_audit_failure_blocks_review_result(execute, request_factory):
    sink = Mock(side_effect=AgentAuditStorageError("unavailable"))
    with patch(
        "app.agent_review_audit_service.make_database_audit_sink",
        return_value=sink,
    ):
        with pytest.raises(AgentAuditStorageError):
            execute(actor(), request_factory())


def test_learning_governance_remains_disabled():
    sink = Mock()
    with patch(
        "app.agent_review_audit_service.make_database_audit_sink",
        return_value=sink,
    ):
        result = execute_audited_learning_review(actor(), learning_request())
    assert result.training_performed is False
    assert result.model_updated is False
    assert result.feedback_persisted is False
    assert result.external_action_performed is False
