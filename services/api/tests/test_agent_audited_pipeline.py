"""Tests for audit delivery and fail-closed behavior."""

from unittest.mock import Mock, patch

import pytest
from fastapi import HTTPException

from app.agent_pipeline import PipelineRequest
from app.agent_audited_pipeline import run_audited_pipeline
from app.security import Principal, Role


def actor():
    return Principal(subject="farmer-a", role=Role.farmer)


def request():
    return PipelineRequest(parcel_id="parcel-1")


def test_success_emits_allowed_event():
    sink = Mock()

    with patch(
        "app.agent_audited_pipeline.prepare_parcel_profile",
        return_value="profile-result",
    ):
        result = run_audited_pipeline(
            Mock(), actor(), request(), sink
        )

    assert result == "profile-result"
    sink.assert_called_once()
    event = sink.call_args.args[0]
    assert event.outcome == "allowed"
    assert event.reason_code == "AUTHORIZED"


def test_denial_emits_denied_event():
    sink = Mock()

    with patch(
        "app.agent_audited_pipeline.prepare_parcel_profile",
        side_effect=HTTPException(404, "Parcel not found"),
    ):
        with pytest.raises(HTTPException) as exc:
            run_audited_pipeline(
                Mock(), actor(), request(), sink
            )

    assert exc.value.status_code == 404
    assert sink.call_args.args[0].outcome == "denied"
    assert sink.call_args.args[0].reason_code == "HTTP_404"


def test_success_audit_failure_blocks_result():
    sink = Mock(side_effect=RuntimeError("Audit unavailable"))

    with patch(
        "app.agent_audited_pipeline.prepare_parcel_profile",
        return_value="profile-result",
    ):
        with pytest.raises(RuntimeError, match="Audit unavailable"):
            run_audited_pipeline(
                Mock(), actor(), request(), sink
            )


def test_denial_audit_failure_is_not_silent():
    sink = Mock(side_effect=RuntimeError("Audit unavailable"))

    with patch(
        "app.agent_audited_pipeline.prepare_parcel_profile",
        side_effect=HTTPException(403, "Denied"),
    ):
        with pytest.raises(RuntimeError, match="Audit unavailable"):
            run_audited_pipeline(
                Mock(), actor(), request(), sink
            )


def test_no_database_commit():
    db = Mock()
    sink = Mock()

    with patch(
        "app.agent_audited_pipeline.prepare_parcel_profile",
        return_value="profile-result",
    ):
        run_audited_pipeline(db, actor(), request(), sink)

    db.commit.assert_not_called()
    db.add.assert_not_called()
