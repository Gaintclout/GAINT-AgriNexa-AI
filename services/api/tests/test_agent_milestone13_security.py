
"""Milestone 13 security and isolated in-process API tests.

No live database connections, external services, or writes to
application databases are permitted by these tests.

Temporary SQLite test resources are created automatically and work
on both Windows and Linux.
"""

import os
import sqlite3
import tempfile
from pathlib import Path
from urllib.parse import unquote, urlsplit

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from app.main import app
from app.agent_preview_router import (
    INTAKE_PROFILE_EXECUTION_APPROVED,
)
from app.learning_agent import (
    FeedbackItem,
    LearningRequest,
    evaluate_learning,
)
from app.escalation_agent_router import (
    router as escalation_router,
)
from app.learning_agent_router import (
    router as learning_router,
)


AGENTS = {
    "weather": "/api/v1/agents/weather/forecast",
    "crop": "/api/v1/agents/crop-advisory/generate",
    "market": "/api/v1/agents/market/prices",
    "schemes": "/api/v1/agents/schemes/screen",
    "escalation": "/api/v1/agents/escalation/screen",
    "learning": "/api/v1/agents/learning/review",
}


@pytest.fixture(scope="module")
def openapi():
    return app.openapi()


@pytest.fixture
def isolated_sqlite(tmp_path_factory):
    """Create a private SQLite database for one test.

    Never reads or modifies application database URLs.
    The temporary directory is created by pytest and is
    independent of any live PostgreSQL database.
    """
    with tempfile.TemporaryDirectory(
        prefix="agrinexa-m13-"
    ) as temporary_directory:
        root = Path(temporary_directory).resolve()
        database = root / "uat.sqlite3"

        sqlite_url = (
            f"sqlite:///{database.as_posix()}"
        )

        yield {
            "root": root,
            "database": database,
            "url": sqlite_url,
        }


def _create_probe_database(database: Path):
    """Initialize a fresh isolated database with only a probe table."""
    assert database.name == "uat.sqlite3"
    assert database.parent.name.startswith("agrinexa-m13-")
    assert database.parent.is_dir()
    assert not database.exists()

    connection = sqlite3.connect(database)

    try:
        connection.execute(
            "CREATE TABLE uat_probe "
            "(id INTEGER PRIMARY KEY, value TEXT)"
        )
        connection.execute(
            "INSERT INTO uat_probe (value) VALUES (?)",
            ("isolated",),
        )
        connection.commit()
    finally:
        connection.close()


@pytest.mark.parametrize("name,path", AGENTS.items())
def test_api_registered(openapi, name, path):
    assert path in openapi["paths"]
    assert "post" in openapi["paths"][path]


@pytest.mark.parametrize("name,path", AGENTS.items())
def test_api_authentication_declared(openapi, name, path):
    operation = openapi["paths"][path]["post"]
    assert operation.get("security"), name


@pytest.mark.parametrize("name,path", AGENTS.items())
def test_api_request_validation_declared(openapi, name, path):
    operation = openapi["paths"][path]["post"]
    assert operation.get("requestBody"), name
    assert "422" in operation.get("responses", {}), name


@pytest.mark.parametrize("name,path", AGENTS.items())
def test_api_success_contract(openapi, name, path):
    operation = openapi["paths"][path]["post"]
    assert "200" in operation["responses"], name


def test_anonymous_learning_request_rejected():
    with TestClient(app) as client:
        response = client.post(
            AGENTS["learning"],
            json={},
        )

    assert response.status_code in (401, 403)


def test_anonymous_escalation_request_rejected():
    with TestClient(app) as client:
        response = client.post(
            AGENTS["escalation"],
            json={},
        )

    assert response.status_code in (401, 403)


def test_learning_rejects_empty_feedback():
    with pytest.raises(ValidationError):
        LearningRequest(
            review_reference="UAT-001",
            feedback=[],
        )


def test_learning_rejects_duplicate_feedback():
    feedback = FeedbackItem(
        feedback_id="FB-001",
        agent_domain="weather",
        recommendation_reference="REC-001",
        outcome="helpful",
        explanation="The recommendation was useful",
    )

    with pytest.raises(ValidationError):
        LearningRequest(
            review_reference="UAT-002",
            feedback=[feedback, feedback],
        )


def test_learning_no_training_or_persistence():
    request = LearningRequest(
        review_reference="UAT-003",
        feedback=[
            FeedbackItem(
                feedback_id="FB-001",
                agent_domain="crop_advisory",
                recommendation_reference="REC-001",
                outcome="incomplete",
                explanation="More supporting field evidence is needed",
            )
        ],
    )

    result = evaluate_learning(request)

    assert result.human_approval_required
    assert not result.training_performed
    assert not result.model_updated
    assert not result.feedback_persisted
    assert not result.external_action_performed


def test_intake_profile_execution_enabled_after_m14():
    assert INTAKE_PROFILE_EXECUTION_APPROVED is True


def test_learning_role_dependency_present():
    from fastapi.routing import APIRoute

    route = next(
        route
        for route in learning_router.routes
        if isinstance(route, APIRoute)
        and route.path.endswith("/review")
    )

    dependencies = route.dependant.dependencies
    assert dependencies


def test_escalation_role_dependency_present():
    from fastapi.routing import APIRoute

    route = next(
        route
        for route in escalation_router.routes
        if isinstance(route, APIRoute)
        and route.path.endswith("/screen")
    )

    assert route.dependant.dependencies


def test_temporary_sqlite_database_is_private(isolated_sqlite):
    """Verify the test database is private and contains probe data."""
    root = isolated_sqlite["root"]
    database = isolated_sqlite["database"]

    assert root.is_dir()
    assert root.name.startswith("agrinexa-m13-")
    assert database.parent == root
    assert database.name == "uat.sqlite3"

    # Do not delete or overwrite any pre-existing database.
    assert not database.exists()

    _create_probe_database(database)

    assert database.is_file()

    connection = sqlite3.connect(database)

    try:
        value = connection.execute(
            "SELECT value FROM uat_probe"
        ).fetchone()[0]

        assert value == "isolated"
    finally:
        connection.close()


def test_isolated_database_contains_only_probe(isolated_sqlite):
    """Ensure the isolated SQLite database contains no app tables."""
    database = isolated_sqlite["database"]

    _create_probe_database(database)

    connection = sqlite3.connect(database)

    try:
        tables = {
            row[0]
            for row in connection.execute(
                "SELECT name FROM sqlite_master "
                "WHERE type='table'"
            )
        }

        assert tables == {"uat_probe"}

        rows = connection.execute(
            "SELECT value FROM uat_probe"
        ).fetchall()

        assert rows == [("isolated",)]
    finally:
        connection.close()


def test_no_live_database_url_in_environment():
    """Prevent accidental execution with database URLs configured."""
    for name in (
        "DATABASE_URL",
        "AGRINEXA_TEST_DATABASE_URL",
        "AGRINEXA_AGENT_AUDIT_TEST_DATABASE_URL",
    ):
        assert not os.environ.get(name), (
            f"{name} must not be configured "
            "for Milestone 13 isolated security tests"
        )


def test_private_sqlite_url(isolated_sqlite):
    """Validate the SQLite URL resolves to the isolated test file."""
    root = isolated_sqlite["root"]
    database = isolated_sqlite["database"]
    url = isolated_sqlite["url"]

    assert root.is_dir()
    assert root.name.startswith("agrinexa-m13-")
    assert database.parent == root
    assert database.name == "uat.sqlite3"

    parsed = urlsplit(url)

    assert parsed.scheme == "sqlite"
    assert parsed.netloc == ""
    assert parsed.query == ""
    assert parsed.fragment == ""

    # SQLite URLs contain the filesystem path after sqlite:///.
    # Handle both Windows drive-letter paths and Linux paths.
    assert url.startswith("sqlite:///")
    assert url.endswith("/uat.sqlite3")

    resolved_path = Path(
        unquote(parsed.path).lstrip("/")
        if os.name == "nt"
        else unquote(parsed.path)
    ).resolve()

    assert resolved_path == database


def test_no_agent_deployment_routes(openapi):
    forbidden = (
        "/api/v1/agents/learning/train",
        "/api/v1/agents/learning/deploy",
        "/api/v1/agents/escalation/dispatch",
    )

    for path in forbidden:
        assert path not in openapi["paths"]
