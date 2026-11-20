"""Milestone 12: static integration, contract and safety tests.

These checks do not connect to a live database, network or server.
"""

from pathlib import Path

import pytest
from pydantic import ValidationError

from app.main import app
from app.agent_preview_router import (
    INTAKE_PROFILE_EXECUTION_APPROVED,
)
from app.escalation_agent import (
    EscalationRequest,
    Evidence,
    evaluate_escalation,
)
from app.learning_agent import (
    FeedbackItem,
    LearningRequest,
    evaluate_learning,
)


ENDPOINTS = {
    "weather": "/api/v1/agents/weather/forecast",
    "crop_advisory": "/api/v1/agents/crop-advisory/generate",
    "market": "/api/v1/agents/market/prices",
    "schemes": "/api/v1/agents/schemes/screen",
    "escalation": "/api/v1/agents/escalation/screen",
    "learning": "/api/v1/agents/learning/review",
}


@pytest.fixture(scope="module")
def schema():
    return app.openapi()


@pytest.mark.parametrize("domain,path", ENDPOINTS.items())
def test_agent_endpoint_registered(schema, domain, path):
    assert path in schema["paths"], domain
    assert "post" in schema["paths"][path], domain


@pytest.mark.parametrize("domain,path", ENDPOINTS.items())
def test_agent_endpoint_authenticated(schema, domain, path):
    endpoint = schema["paths"][path]["post"]
    assert endpoint.get("security"), domain


@pytest.mark.parametrize("domain,path", ENDPOINTS.items())
def test_agent_request_schema_present(schema, domain, path):
    endpoint = schema["paths"][path]["post"]
    assert endpoint.get("requestBody"), domain


@pytest.mark.parametrize("domain,path", ENDPOINTS.items())
def test_agent_response_schema_present(schema, domain, path):
    endpoint = schema["paths"][path]["post"]
    assert endpoint.get("responses"), domain
    assert "200" in endpoint["responses"], domain


@pytest.mark.parametrize("domain,path", ENDPOINTS.items())
def test_agent_json_response(schema, domain, path):
    response = schema["paths"][path]["post"][
        "responses"
    ]["200"]
    assert "application/json" in response.get("content", {})


def test_all_agent_paths_unique(schema):
    paths = list(ENDPOINTS.values())
    assert len(paths) == len(set(paths))
    assert all(path in schema["paths"] for path in paths)


def test_intake_execution_enabled_after_m14():
    assert INTAKE_PROFILE_EXECUTION_APPROVED is True


def test_escalation_no_autonomous_actions():
    request = EscalationRequest(
        case_reference="UAT-ESC-001",
        indicators=[
            Evidence(
                indicator="severe_weather",
                description="Heavy rainfall observed in field",
                source_type="field_observation",
            )
        ],
    )

    result = evaluate_escalation(request)

    assert result.human_review_required
    assert result.advisory_only
    assert not result.external_action_performed
    assert not result.notifications_sent
    assert not result.official_emergency_assessment


def test_escalation_invalid_input_rejected():
    with pytest.raises(ValidationError):
        EscalationRequest(
            case_reference="X",
            indicators=[],
        )


def test_learning_no_autonomous_training():
    request = LearningRequest(
        review_reference="UAT-LEARN-001",
        feedback=[
            FeedbackItem(
                feedback_id="FB-001",
                agent_domain="crop_advisory",
                recommendation_reference="REC-001",
                outcome="incomplete",
                explanation="Recommendation needs more field context",
            )
        ],
    )

    result = evaluate_learning(request)

    assert result.human_approval_required
    assert result.advisory_only
    assert not result.training_performed
    assert not result.model_updated
    assert not result.feedback_persisted
    assert not result.external_action_performed


def test_learning_duplicate_feedback_rejected():
    feedback = FeedbackItem(
        feedback_id="FB-001",
        agent_domain="weather",
        recommendation_reference="REC-001",
        outcome="helpful",
        explanation="Forecast guidance was useful",
    )

    with pytest.raises(ValidationError):
        LearningRequest(
            review_reference="UAT-LEARN-002",
            feedback=[feedback, feedback],
        )


def test_frontend_governance_integrations():
    root = Path(__file__).resolve().parents[3]
    governance = (
        root / "apps/web/src/AgentGovernance.jsx"
    ).read_text()

    components = [
        "AgentWeatherWorkspace",
        "AgentCropAdvisoryWorkspace",
        "AgentMarketWorkspace",
        "AgentSchemeWorkspace",
        "AgentEscalationWorkspace",
        "AgentLearningWorkspace",
    ]

    for component in components:
        assert component in governance, component
        assert (root / f"apps/web/src/{component}.jsx").is_file()


def test_learning_frontend_api_reference():
    root = Path(__file__).resolve().parents[3]
    source = (
        root / "apps/web/src/AgentLearningWorkspace.jsx"
    ).read_text()
    assert "/api/v1/agents/learning/review" in source


def test_escalation_frontend_api_reference():
    root = Path(__file__).resolve().parents[3]
    source = (
        root / "apps/web/src/AgentEscalationWorkspace.jsx"
    ).read_text()
    assert "/api/v1/agents/escalation/screen" in source


def test_no_agent_training_or_dispatch_routes(schema):
    forbidden = (
        "/api/v1/agents/learning/train",
        "/api/v1/agents/learning/deploy",
        "/api/v1/agents/escalation/dispatch",
        "/api/v1/agents/escalation/notify",
    )
    for path in forbidden:
        assert path not in schema["paths"]


def test_milestone11_and_10_tests_present():
    root = Path(__file__).resolve().parents[3]
    for name in (
        "test_escalation_agent.py",
        "test_escalation_agent_router.py",
        "test_learning_agent.py",
        "test_learning_agent_router.py",
    ):
        assert (
            root / "services/api/tests" / name
        ).is_file()
