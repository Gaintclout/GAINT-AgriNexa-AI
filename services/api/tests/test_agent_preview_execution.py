"""Security tests for the governed Intake/Profile execution path."""

from unittest.mock import Mock, patch

import pytest
from fastapi import HTTPException

from app.agent_pipeline import PipelineRequest
from app.agent_preview_router import preview_intake_profile
from app.security import Principal, Role


def actor():
    return Principal(subject="admin-1", role=Role.admin)


def active_db():
    db = Mock()
    db.get.return_value = Mock(
        is_active=True,
        role="admin",
    )
    return db


def test_execution_disabled_when_approval_revoked():
    with (
        patch("app.agent_preview_router.INTAKE_PROFILE_EXECUTION_APPROVED", False),
        patch("app.agent_preview_router.execute_audited_intake_profile") as execute,
    ):
        with pytest.raises(HTTPException) as exc:
            preview_intake_profile(
                PipelineRequest(parcel_id="parcel-1"),
                actor(),
                active_db(),
            )

    assert exc.value.status_code == 503
    execute.assert_not_called()


def test_inactive_account_rejected():
    db = active_db()
    db.get.return_value.is_active = False

    with pytest.raises(HTTPException) as exc:
        preview_intake_profile(
            PipelineRequest(parcel_id="parcel-1"),
            actor(),
            db,
        )

    assert exc.value.status_code == 401


def test_approved_path_calls_audited_service():
    with (
        patch(
            "app.agent_preview_router.INTAKE_PROFILE_EXECUTION_APPROVED",
            True,
        ),
        patch(
            "app.agent_preview_router.execute_audited_intake_profile",
            return_value="profile-result",
        ) as execute,
    ):
        result = preview_intake_profile(
            PipelineRequest(parcel_id="parcel-1"),
            actor(),
            active_db(),
        )

    assert result == "profile-result"
    execute.assert_called_once()


def test_audit_failure_blocks_profile():
    from app.agent_audit_sink import AgentAuditStorageError

    with (
        patch(
            "app.agent_preview_router.INTAKE_PROFILE_EXECUTION_APPROVED",
            True,
        ),
        patch(
            "app.agent_preview_router.execute_audited_intake_profile",
            side_effect=AgentAuditStorageError(
                "Audit unavailable"
            ),
        ),
    ):
        with pytest.raises(HTTPException) as exc:
            preview_intake_profile(
                PipelineRequest(parcel_id="parcel-1"),
                actor(),
                active_db(),
            )

    assert exc.value.status_code == 503
