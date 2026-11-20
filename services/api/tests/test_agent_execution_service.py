"""Tests for mandatory audit wiring in the internal execution service."""

from unittest.mock import Mock, patch

import pytest

from app.agent_execution_service import execute_audited_intake_profile
from app.agent_pipeline import PipelineRequest
from app.security import Principal, Role


def actor():
    return Principal(subject="farmer-a", role=Role.farmer)


def request():
    return PipelineRequest(parcel_id="parcel-1")


def test_execution_uses_persistent_audit_sink():
    db = Mock()
    sink = Mock()

    with (
        patch(
            "app.agent_execution_service.make_database_audit_sink",
            return_value=sink,
        ) as sink_factory,
        patch(
            "app.agent_execution_service.run_audited_pipeline",
            return_value="profile-result",
        ) as pipeline,
    ):
        result = execute_audited_intake_profile(
            db,
            actor(),
            request(),
        )

    assert result == "profile-result"
    sink_factory.assert_called_once()
    pipeline.assert_called_once()

    assert pipeline.call_args.args[0] is db
    assert pipeline.call_args.args[3] is sink


def test_audit_failure_prevents_result():
    db = Mock()

    with patch(
        "app.agent_execution_service.make_database_audit_sink",
        side_effect=RuntimeError("Audit unavailable"),
    ):
        with pytest.raises(RuntimeError, match="Audit unavailable"):
            execute_audited_intake_profile(
                db,
                actor(),
                request(),
            )


def test_pipeline_failure_is_not_suppressed():
    db = Mock()

    with (
        patch(
            "app.agent_execution_service.make_database_audit_sink",
            return_value=Mock(),
        ),
        patch(
            "app.agent_execution_service.run_audited_pipeline",
            side_effect=RuntimeError("Pipeline unavailable"),
        ),
    ):
        with pytest.raises(RuntimeError, match="Pipeline unavailable"):
            execute_audited_intake_profile(
                db,
                actor(),
                request(),
            )
