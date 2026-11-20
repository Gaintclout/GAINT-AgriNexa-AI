from unittest.mock import Mock, patch

import pytest
from fastapi import HTTPException

from app.escalation_agent import (
    EscalationRequest,
    Evidence,
    Indicator,
)
from app.escalation_agent_router import screen_escalation


def payload():
    return EscalationRequest(
        case_reference="CASE-001",
        indicators=[
            Evidence(
                indicator=Indicator.crop_damage,
                description="Documented agricultural field observation",
                source_type="field_observation",
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
        screen_escalation(payload(), principal(), db)
    assert error.value.status_code == 401


def test_inactive_user_rejected():
    db = Mock()
    db.get.return_value = Mock(
        is_active=False,
        role="admin",
    )
    with pytest.raises(HTTPException) as error:
        screen_escalation(payload(), principal(), db)
    assert error.value.status_code == 401


def test_role_mismatch_rejected():
    db = Mock()
    db.get.return_value = Mock(
        is_active=True,
        role="farmer",
    )
    with pytest.raises(HTTPException) as error:
        screen_escalation(payload(), principal(), db)
    assert error.value.status_code == 401


def test_authorized_admin():
    db = Mock()
    db.get.return_value = Mock(
        is_active=True,
        role="admin",
    )
    expected = Mock(
        case_reference="CASE-001",
        human_review_required=True,
        external_action_performed=False,
    )
    with patch(
        "app.escalation_agent_router.execute_audited_escalation_review",
        return_value=expected,
    ) as execute:
        result = screen_escalation(payload(), principal(), db)
    execute.assert_called_once()
    assert result.case_reference == "CASE-001"
    assert result.human_review_required
    assert not result.external_action_performed


def test_authorized_ml_team():
    db = Mock()
    db.get.return_value = Mock(
        is_active=True,
        role="ml_team",
    )
    expected = Mock(priority_score=25)
    with patch(
        "app.escalation_agent_router.execute_audited_escalation_review",
        return_value=expected,
    ):
        result = screen_escalation(
            payload(),
            principal("ml_team"),
            db,
        )
    assert result.priority_score == 25


def test_openapi_security_and_route():
    from app.main import app

    schema = app.openapi()
    endpoint = schema["paths"][
        "/api/v1/agents/escalation/screen"
    ]["post"]

    assert endpoint.get("security")
    assert endpoint.get("requestBody")


def test_audit_failure_returns_503():
    from app.agent_audit_sink import AgentAuditStorageError
    db = Mock()
    db.get.return_value = Mock(is_active=True, role="admin")
    with patch(
        "app.escalation_agent_router.execute_audited_escalation_review",
        side_effect=AgentAuditStorageError("unavailable"),
    ):
        with pytest.raises(HTTPException) as error:
            screen_escalation(payload(), principal(), db)
    assert error.value.status_code == 503
