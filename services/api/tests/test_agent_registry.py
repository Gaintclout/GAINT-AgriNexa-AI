
"""Security and API contract tests for the governed AI agent registry.

Verifies:
- Authentication and role-based authorization.
- Active-account and database-role validation.
- Registry discovery and individual agent lookup.
- Intake/Profile configured execution approval.
- Approval revocation and fail-closed capability reporting.
- Generic execution denial for every registered agent.
- Automatic learning remains disabled.
"""

from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from app import agent_preview_router
from app.database import get_db
from app.main import app
from app.security import Role, create_access_token


AGENT_NAMES = (
    "INTAKE",
    "PROFILE",
    "WEATHER",
    "CROP_ADVISORY",
    "MARKET",
    "SCHEME",
    "ESCALATION",
    "LEARNING",
)

INTAKE_PROFILE_AGENTS = (
    "INTAKE",
    "PROFILE",
)

OTHER_AGENTS = tuple(
    name
    for name in AGENT_NAMES
    if name not in INTAKE_PROFILE_AGENTS
)

AUTHORIZED_ROLES = (
    Role.admin,
    Role.gis_operator,
    Role.ml_team,
)

UNAUTHORIZED_ROLES = (
    Role.farmer,
    Role.field_verifier,
    Role.officer,
)


class FakeDB:
    """Minimal database substitute for account verification."""

    def __init__(
        self,
        role="admin",
        active=True,
        exists=True,
    ):
        self.role = role
        self.active = active
        self.exists = exists

    def get(self, model, subject):
        if not self.exists:
            return None

        return SimpleNamespace(
            id=subject,
            role=self.role,
            is_active=self.active,
        )


@pytest.fixture
def client(monkeypatch):
    """Create an isolated API test client."""

    monkeypatch.setenv(
        "AGRINEXA_JWT_SECRET",
        "agent-registry-test-secret-32-characters-long",
    )

    # Ensure the approval state is deterministic for each test.
    monkeypatch.setattr(
        agent_preview_router,
        "INTAKE_PROFILE_EXECUTION_APPROVED",
        True,
    )

    app.dependency_overrides[get_db] = lambda: FakeDB()

    try:
        with TestClient(app) as test_client:
            yield test_client
    finally:
        app.dependency_overrides.clear()


def headers(role):
    token = create_access_token(
        "test-user",
        role,
    )

    return {
        "Authorization": f"Bearer {token}",
    }


def assert_agent_capabilities(
    agent,
    *,
    enabled,
):
    """Validate the registry capability contract."""

    assert agent["status"] == (
        "enabled" if enabled else "disabled"
    )

    assert agent["execution_enabled"] is enabled

    # Model learning/training is never automatically enabled.
    assert agent["learning_enabled"] is False


# --------------------------------------------------
# Authentication tests
# --------------------------------------------------

def test_unauthenticated_access_denied(client):
    response = client.get("/api/v1/agents")

    assert response.status_code == 401


@pytest.mark.parametrize(
    "role",
    UNAUTHORIZED_ROLES,
)
def test_unauthorized_roles_denied(client, role):
    response = client.get(
        "/api/v1/agents",
        headers=headers(role),
    )

    assert response.status_code == 403


def test_invalid_token_denied(client):
    response = client.get(
        "/api/v1/agents",
        headers={
            "Authorization": "Bearer invalid-token",
        },
    )

    assert response.status_code == 401


# --------------------------------------------------
# Authorized registry access
# --------------------------------------------------

@pytest.mark.parametrize(
    "role",
    AUTHORIZED_ROLES,
)
def test_authorized_roles_can_read_registry(
    client,
    role,
):
    app.dependency_overrides[get_db] = (
        lambda: FakeDB(role=role.value)
    )

    response = client.get(
        "/api/v1/agents",
        headers=headers(role),
    )

    assert response.status_code == 200

    agents = response.json()

    assert len(agents) == len(AGENT_NAMES)

    agents_by_id = {
        agent["id"]: agent
        for agent in agents
    }

    assert set(agents_by_id) == set(AGENT_NAMES)

    # Intake/Profile have approved preview execution.
    for name in INTAKE_PROFILE_AGENTS:
        assert_agent_capabilities(
            agents_by_id[name],
            enabled=True,
        )

    # Other agents are not enabled in the generic registry.
    for name in OTHER_AGENTS:
        assert_agent_capabilities(
            agents_by_id[name],
            enabled=False,
        )


# --------------------------------------------------
# Account state verification
# --------------------------------------------------

def test_inactive_account_denied(client):
    app.dependency_overrides[get_db] = (
        lambda: FakeDB(active=False)
    )

    response = client.get(
        "/api/v1/agents",
        headers=headers(Role.admin),
    )

    assert response.status_code == 401


def test_deleted_account_denied(client):
    app.dependency_overrides[get_db] = (
        lambda: FakeDB(exists=False)
    )

    response = client.get(
        "/api/v1/agents",
        headers=headers(Role.admin),
    )

    assert response.status_code == 401


def test_role_mismatch_denied(client):
    app.dependency_overrides[get_db] = (
        lambda: FakeDB(role="farmer")
    )

    response = client.get(
        "/api/v1/agents",
        headers=headers(Role.admin),
    )

    assert response.status_code == 401


# --------------------------------------------------
# Individual agent lookup
# --------------------------------------------------

def test_single_agent_lookup(client):
    response = client.get(
        "/api/v1/agents/INTAKE",
        headers=headers(Role.admin),
    )

    assert response.status_code == 200

    agent = response.json()

    assert agent["id"] == "INTAKE"

    assert_agent_capabilities(
        agent,
        enabled=True,
    )


@pytest.mark.parametrize(
    "agent_id",
    AGENT_NAMES,
)
def test_each_registered_agent_lookup(
    client,
    agent_id,
):
    response = client.get(
        f"/api/v1/agents/{agent_id}",
        headers=headers(Role.admin),
    )

    assert response.status_code == 200

    agent = response.json()

    assert agent["id"] == agent_id

    assert_agent_capabilities(
        agent,
        enabled=agent_id in INTAKE_PROFILE_AGENTS,
    )


def test_lowercase_agent_lookup(client):
    response = client.get(
        "/api/v1/agents/intake",
        headers=headers(Role.admin),
    )

    assert response.status_code == 200

    agent = response.json()

    assert agent["id"] == "INTAKE"

    assert_agent_capabilities(
        agent,
        enabled=True,
    )


def test_unknown_agent_returns_404(client):
    response = client.get(
        "/api/v1/agents/UNKNOWN",
        headers=headers(Role.admin),
    )

    assert response.status_code == 404


# --------------------------------------------------
# Approval revocation tests
# --------------------------------------------------

def test_registry_disables_intake_profile_when_approval_revoked(
    client,
    monkeypatch,
):
    monkeypatch.setattr(
        agent_preview_router,
        "INTAKE_PROFILE_EXECUTION_APPROVED",
        False,
    )

    response = client.get(
        "/api/v1/agents",
        headers=headers(Role.admin),
    )

    assert response.status_code == 200

    agents = {
        agent["id"]: agent
        for agent in response.json()
    }

    assert set(agents) == set(AGENT_NAMES)

    for name in AGENT_NAMES:
        assert_agent_capabilities(
            agents[name],
            enabled=False,
        )


@pytest.mark.parametrize(
    "agent_id",
    INTAKE_PROFILE_AGENTS,
)
def test_individual_agent_disabled_when_approval_revoked(
    client,
    monkeypatch,
    agent_id,
):
    monkeypatch.setattr(
        agent_preview_router,
        "INTAKE_PROFILE_EXECUTION_APPROVED",
        False,
    )

    response = client.get(
        f"/api/v1/agents/{agent_id}",
        headers=headers(Role.admin),
    )

    assert response.status_code == 200

    agent = response.json()

    assert agent["id"] == agent_id

    assert_agent_capabilities(
        agent,
        enabled=False,
    )


def test_preview_availability_follows_approval(
    client,
    monkeypatch,
):
    monkeypatch.setattr(
        agent_preview_router,
        "INTAKE_PROFILE_EXECUTION_APPROVED",
        False,
    )

    response = client.get(
        "/api/v1/agents/intake-profile/availability",
        headers=headers(Role.admin),
    )

    assert response.status_code == 200
    assert response.json()["available"] is False


# --------------------------------------------------
# Generic execution authentication
# --------------------------------------------------

def test_execution_requires_authentication(client):
    response = client.post(
        "/api/v1/agents/INTAKE/execute",
    )

    assert response.status_code == 401


def test_execution_rejects_unauthorized_role(client):
    response = client.post(
        "/api/v1/agents/INTAKE/execute",
        headers=headers(Role.farmer),
    )

    assert response.status_code == 403


def test_execution_rejects_inactive_account(client):
    app.dependency_overrides[get_db] = (
        lambda: FakeDB(active=False)
    )

    response = client.post(
        "/api/v1/agents/INTAKE/execute",
        headers=headers(Role.admin),
    )

    assert response.status_code == 401


def test_execution_rejects_unknown_agent(client):
    response = client.post(
        "/api/v1/agents/UNKNOWN/execute",
        headers=headers(Role.admin),
    )

    assert response.status_code == 404


# --------------------------------------------------
# Generic execution must remain disabled
# --------------------------------------------------

@pytest.mark.parametrize(
    "agent_id",
    AGENT_NAMES,
)
def test_execution_disabled_for_every_agent(
    client,
    agent_id,
):
    response = client.post(
        f"/api/v1/agents/{agent_id}/execute",
        headers=headers(Role.admin),
    )

    assert response.status_code == 403

    assert (
        response.json()["detail"]
        == "Agent execution is disabled"
    )


@pytest.mark.parametrize(
    "agent_id",
    INTAKE_PROFILE_AGENTS,
)
def test_generic_execution_remains_disabled_when_preview_approved(
    client,
    agent_id,
):
    """Preview approval must not enable generic execution."""

    response = client.post(
        f"/api/v1/agents/{agent_id}/execute",
        headers=headers(Role.admin),
    )

    assert response.status_code == 403

    assert (
        response.json()["detail"]
        == "Agent execution is disabled"
    )


@pytest.mark.parametrize(
    "agent_id",
    INTAKE_PROFILE_AGENTS,
)
def test_generic_execution_disabled_after_approval_revocation(
    client,
    monkeypatch,
    agent_id,
):
    monkeypatch.setattr(
        agent_preview_router,
        "INTAKE_PROFILE_EXECUTION_APPROVED",
        False,
    )

    response = client.post(
        f"/api/v1/agents/{agent_id}/execute",
        headers=headers(Role.admin),
    )

    assert response.status_code == 403

    assert (
        response.json()["detail"]
        == "Agent execution is disabled"
    )
