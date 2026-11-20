"""Tests for independent agent audit persistence."""

from unittest.mock import Mock

import pytest

from app.agent_audit import build_audit_event
from app.agent_audit_sink import (
    AgentAuditStorageError,
    make_database_audit_sink,
)
from app.security import Principal, Role


def event():
    return build_audit_event(
        Principal(subject="farmer-a", role=Role.farmer),
        "parcel-1",
        allowed=True,
        reason_code="AUTHORIZED",
    )


def session_fixture():
    session = Mock()
    session.__enter__ = Mock(return_value=session)
    session.__exit__ = Mock(return_value=False)
    factory = Mock(return_value=session)
    from unittest.mock import MagicMock
    factory.return_value.return_value = MagicMock()
    factory.return_value.return_value.__enter__.return_value = session
    return factory, session


def test_successful_audit_commit():
    factory, session = session_fixture()

    sink = make_database_audit_sink(factory)
    sink(event())

    factory.assert_called_once()
    session.add.assert_called_once()
    session.commit.assert_called_once()
    session.rollback.assert_not_called()

    record = session.add.call_args.args[0]
    assert record.actor_id == "farmer-a"
    assert record.parcel_id == "parcel-1"
    assert record.outcome == "allowed"


def test_commit_failure_rolls_back():
    factory, session = session_fixture()
    session.commit.side_effect = RuntimeError("database error")

    sink = make_database_audit_sink(factory)

    with pytest.raises(AgentAuditStorageError):
        sink(event())

    session.rollback.assert_called_once()


def test_session_creation_failure():
    factory = Mock(side_effect=RuntimeError("connection unavailable"))

    sink = make_database_audit_sink(factory)

    with pytest.raises(AgentAuditStorageError):
        sink(event())


def test_no_automatic_connection():
    factory = Mock()

    make_database_audit_sink(factory)

    factory.assert_not_called()


def test_separate_session_for_each_event():
    factory, session = session_fixture()
    sink = make_database_audit_sink(factory)

    sink(event())
    sink(event())

    assert factory.call_count == 2
    assert session.commit.call_count == 2


def test_denied_event_persisted():
    factory, session = session_fixture()

    denied = build_audit_event(
        Principal(subject="farmer-a", role=Role.farmer),
        "parcel-2",
        allowed=False,
        reason_code="HTTP_404",
    )

    make_database_audit_sink(factory)(denied)

    record = session.add.call_args.args[0]
    assert record.outcome == "denied"
    assert record.reason_code == "HTTP_404"
