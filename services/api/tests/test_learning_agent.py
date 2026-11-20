from datetime import datetime, timedelta, timezone

import pytest
from pydantic import ValidationError

from app.learning_agent import (
    AgentDomain,
    FeedbackEvidence,
    FeedbackItem,
    FeedbackOutcome,
    LearningRequest,
    evaluate_learning,
)


def evidence(verified=False, **kwargs):
    values = {
        "description": "Documented agricultural field observation",
        "source_type": "field_observation",
        "source_reference": "SOURCE-001" if verified else None,
        "verified": verified,
    }
    values.update(kwargs)
    return FeedbackEvidence(**values)


def item(
    outcome=FeedbackOutcome.incomplete,
    evidence_items=None,
    **kwargs,
):
    values = {
        "feedback_id": "FB-001",
        "agent_domain": AgentDomain.crop_advisory,
        "recommendation_reference": "REC-001",
        "outcome": outcome,
        "explanation": "Recommendation requires additional review",
        "evidence": evidence_items or [],
    }
    values.update(kwargs)
    return FeedbackItem(**values)


def review(*items):
    return LearningRequest(
        review_reference="REVIEW-001",
        feedback=list(items),
    )


def test_helpful_with_verified_evidence():
    result = evaluate_learning(
        review(
            item(
                FeedbackOutcome.helpful,
                [evidence(verified=True)],
            )
        )
    )
    assert result.findings[0].assessment == "positive_feedback"


def test_inaccurate_feedback_requires_review():
    result = evaluate_learning(
        review(
            item(
                FeedbackOutcome.inaccurate,
                [evidence(verified=True)],
            )
        )
    )
    assert result.findings[0].assessment == "review_required"
    assert result.review_priority == "priority"


def test_incomplete_without_evidence():
    result = evaluate_learning(review(item()))
    assert result.findings[0].assessment == "insufficient_evidence"


def test_outdated_feedback():
    result = evaluate_learning(
        review(
            item(
                FeedbackOutcome.outdated,
                [evidence(verified=True)],
            )
        )
    )
    assert result.review_priority == "priority"


def test_unsafe_feedback_urgent():
    result = evaluate_learning(
        review(item(FeedbackOutcome.unsafe))
    )
    assert result.review_priority == "urgent"
    assert result.findings[0].assessment == "safety_review_required"


def test_verified_evidence_status():
    result = evaluate_learning(
        review(item(evidence_items=[evidence(verified=True)]))
    )
    assert result.findings[0].evidence_status == "source_referenced"


def test_unverified_evidence_status():
    result = evaluate_learning(
        review(item(evidence_items=[evidence()]))
    )
    assert result.findings[0].evidence_status == "unverified"


def test_partially_referenced_evidence():
    result = evaluate_learning(
        review(
            item(
                evidence_items=[
                    evidence(verified=True),
                    evidence(),
                ]
            )
        )
    )
    assert result.findings[0].evidence_status == "partially_referenced"


def test_missing_evidence_status():
    result = evaluate_learning(review(item()))
    assert result.findings[0].evidence_status == "no_evidence"


def test_duplicate_feedback_ids_rejected():
    with pytest.raises(ValidationError):
        review(item(), item())


def test_empty_feedback_rejected():
    with pytest.raises(ValidationError):
        review()


def test_more_than_25_feedback_rejected():
    with pytest.raises(ValidationError):
        review(
            *[
                item(feedback_id=f"FB-{index:03d}")
                for index in range(26)
            ]
        )


def test_verified_requires_reference():
    with pytest.raises(ValidationError):
        evidence(verified=True, source_reference=None)


def test_future_evidence_rejected():
    with pytest.raises(ValidationError):
        evidence(
            observed_at=datetime.now(timezone.utc)
            + timedelta(days=1)
        )


def test_naive_timestamp_rejected():
    with pytest.raises(ValidationError):
        evidence(observed_at=datetime.now())


def test_short_explanation_rejected():
    with pytest.raises(ValidationError):
        item(explanation="short")


def test_extra_fields_rejected():
    with pytest.raises(ValidationError):
        item(automatic_training=True)


def test_all_agent_domains_supported():
    for domain in AgentDomain:
        result = evaluate_learning(
            review(item(agent_domain=domain))
        )
        assert result.findings[0].agent_domain == domain


def test_no_training_or_model_update():
    result = evaluate_learning(review(item()))
    assert not result.training_performed
    assert not result.model_updated
    assert not result.feedback_persisted
    assert not result.external_action_performed
    assert result.human_approval_required


def test_proposals_deduplicated():
    result = evaluate_learning(
        review(
            item(feedback_id="FB-001"),
            item(feedback_id="FB-002"),
        )
    )
    assert len(result.improvement_proposals) == 2


def test_feedback_count():
    result = evaluate_learning(
        review(
            item(feedback_id="FB-001"),
            item(feedback_id="FB-002"),
        )
    )
    assert result.feedback_count == 2


def test_disclaimer():
    result = evaluate_learning(review(item()))
    assert "not autonomous" in result.disclaimer
    assert result.advisory_only
