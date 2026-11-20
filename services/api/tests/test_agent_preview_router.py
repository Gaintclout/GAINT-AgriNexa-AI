"""Tests for the disabled, authenticated Intake/Profile preview."""

from fastapi import HTTPException
from unittest.mock import Mock

class MockDb:
    def get(self, model, subject):
        return Mock(
            is_active=True,
            role="admin",
        )

import pytest

from app.agent_pipeline import PipelineRequest
from app.agent_preview_router import (
    PreviewAvailability,
    preview_intake_profile,
)


def test_preview_defaults_to_unavailable():
    status = PreviewAvailability()

    assert status.available is False
    assert "audit" in status.reason.lower()


def test_preview_fails_closed():
    request = PipelineRequest(parcel_id="parcel-1")

    with pytest.raises(HTTPException) as exc:
        preview_intake_profile(
            request,
            Mock(subject="admin-1", role=Mock(value="admin")),
            MockDb(),
        )

    assert exc.value.status_code == 503


def test_preview_request_rejects_missing_parcel():
    with pytest.raises(ValueError):
        PipelineRequest(parcel_id="")


def test_preview_request_rejects_extra_fields():
    with pytest.raises(ValueError):
        PipelineRequest(
            parcel_id="parcel-1",
            unsupported_field="value",
        )
