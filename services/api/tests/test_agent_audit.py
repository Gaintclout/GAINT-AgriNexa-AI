"""Tests for minimal, non-persistent audit events."""

from datetime import timezone

import pytest
from pydantic import ValidationError

from app.agent_audit import AgentAuditEvent, build_audit_event
from app.security import Principal, Role


def actor():
    return Principal(subject="farmer-a", role=Role.farmer)


def test_allowed_event():
    event = build_audit_event(
        actor(),
        "parcel-1",
        allowed=True,
        reason_code="AUTHORIZED",
    )
    assert event.outcome == "allowed"
    assert event.actor_id == "farmer-a"
    assert event.operation == "INTAKE_PROFILE"


def test_denied_event():
    event = build_audit_event(
        actor(),
        "parcel-2",
        allowed=False,
        reason_code="ACCESS_DENIED",
    )
    assert event.outcome == "denied"
    assert event.reason_code == "ACCESS_DENIED"


def test_timestamp_is_utc():
    event = build_audit_event(
        actor(),
        "parcel-1",
        allowed=True,
        reason_code="AUTHORIZED",
    )
    assert event.timestamp.tzinfo is not None
    assert event.timestamp.utcoffset().total_seconds() == 0


def test_sensitive_fields_not_present():
    event = build_audit_event(
        actor(),
        "parcel-1",
        allowed=True,
        reason_code="AUTHORIZED",
    )
    data = event.model_dump()
    for field in ("password", "token", "crop_name", "season"):
        assert field not in data


def test_invalid_outcome_rejected():
    event = build_audit_event(
        actor(),
        "parcel-1",
        allowed=True,
        reason_code="AUTHORIZED",
    )
    data = event.model_dump()
    data["outcome"] = "unknown"
    with pytest.raises(ValidationError):
        AgentAuditEvent(**data)
