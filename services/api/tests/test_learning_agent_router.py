from unittest.mock import Mock, patch

import pytest
from fastapi import HTTPException

from app.learning_agent import (
    FeedbackItem,
    LearningRequest,
)
from app.learning_agent_router import review_learning


def payload():
    return LearningRequest(
        review_reference="REVIEW-001",
        feedback=[
            FeedbackItem(
                feedback_id="FB-001",
                agent_domain="crop_advisory",
                recommendation_reference="REC-001",
                outcome="incomplete",
                explanation="Recommendation requires additional review",
            )
        ],
    )


def principal(role="admin"):
    return Mock(
        subject="user-001",
        role=Mock(value=role),
    )


def test_missing_user_rejected():
    db = Mock()
    db.get.return_value = None

    with pytest.raises(HTTPException) as error:
        review_learning(payload(), principal(), db)

    assert error.value.status_code == 401


def test_inactive_user_rejected():
    db = Mock()
    db.get.return_value = Mock(
        is_active=False,
        role="admin",
    )

    with pytest.raises(HTTPException) as error:
        review_learning(payload(), principal(), db)

    assert error.value.status_code == 401


def test_role_mismatch_rejected():
    db = Mock()
    db.get.return_value = Mock(
        is_active=True,
        role="farmer",
    )

    with pytest.raises(HTTPException) as error:
        review_learning(payload(), principal(), db)

    assert error.value.status_code == 401


def test_authorized_admin():
    db = Mock()
    db.get.return_value = Mock(
        is_active=True,
        role="admin",
    )

    expected = Mock(
        feedback_count=1,
        human_approval_required=True,
        training_performed=False,
    )
    with patch(
        "app.learning_agent_router.execute_audited_learning_review",
        return_value=expected,
    ) as execute:
        result = review_learning(payload(), principal(), db)
    execute.assert_called_once()

    assert result.feedback_count == 1
    assert result.human_approval_required
    assert not result.training_performed


def test_authorized_ml_team():
    db = Mock()
    db.get.return_value = Mock(
        is_active=True,
        role="ml_team",
    )

    expected = Mock(feedback_count=1)
    with patch(
        "app.learning_agent_router.execute_audited_learning_review",
        return_value=expected,
    ):
        result = review_learning(
            payload(),
            principal("ml_team"),
            db,
        )

    assert result.feedback_count == 1


def test_openapi_security():
    from app.main import app

    endpoint = app.openapi()["paths"][
        "/api/v1/agents/learning/review"
    ]["post"]

    assert endpoint.get("security")
    assert endpoint.get("requestBody")


def test_audit_failure_returns_503():
    from app.agent_audit_sink import AgentAuditStorageError
    db = Mock()
    db.get.return_value = Mock(is_active=True, role="admin")
    with patch(
        "app.learning_agent_router.execute_audited_learning_review",
        side_effect=AgentAuditStorageError("unavailable"),
    ):
        with pytest.raises(HTTPException) as error:
            review_learning(payload(), principal(), db)
    assert error.value.status_code == 503
