"""M15 persistent authentication security regression tests."""

from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import Mock, patch

import pytest
from fastapi import HTTPException, Response
from starlette.requests import Request

from app import auth_router


class FakeResult:
    def __init__(self, row=None):
        self.row = row

    def first(self):
        return self.row


class FakeDatabase:
    def __init__(self):
        self.sessions = {}
        self.users = {
            "user-1": SimpleNamespace(
                id="user-1",
                role="farmer",
                is_active=True,
            )
        }
        self.commits = 0
        self.rollbacks = 0

    def execute(self, statement, params):
        sql = str(statement).upper()

        if "INSERT INTO AUTH_REFRESH_SESSIONS" in sql:
            self.sessions[params["digest"]] = {
                "user_id": params["uid"],
                "expires": params["expires"],
                "revoked": False,
            }
            return FakeResult()

        if "UPDATE AUTH_REFRESH_SESSIONS" in sql:
            session = self.sessions.get(params["digest"])

            if (
                session is None
                or session["revoked"]
                or (
                    "EXPIRES_AT >" in sql
                    and session["expires"] <= params["now"]
                )
            ):
                return FakeResult()

            session["revoked"] = True

            if "RETURNING USER_ID" in sql:
                return FakeResult((session["user_id"],))

            return FakeResult()

        raise AssertionError(f"Unexpected SQL: {sql}")

    def get(self, model, user_id):
        return self.users.get(user_id)

    def commit(self):
        self.commits += 1

    def rollback(self):
        self.rollbacks += 1


def make_request(token=None, origin="https://agrinexa-test.gaintclout.com"):
    headers = [(b"origin", origin.encode())]

    if token:
        headers.append((
            b"cookie",
            f"{auth_router._REFRESH_COOKIE}={token}".encode(),
        ))

    return Request({
        "type": "http",
        "method": "POST",
        "path": "/api/v1/auth/refresh",
        "headers": headers,
        "scheme": "https",
        "server": ("agrinexa-test.gaintclout.com", 443),
        "client": ("127.0.0.1", 12345),
    })


def cookie_value(response):
    cookies = response.headers.getlist("set-cookie")

    for cookie in cookies:
        prefix = auth_router._REFRESH_COOKIE + "="
        if cookie.startswith(prefix):
            return cookie.split(";", 1)[0].split("=", 1)[1]

    return None


@pytest.fixture
def environment(monkeypatch):
    monkeypatch.setattr(
        auth_router,
        "_origin_guard",
        lambda request: None,
    )
    monkeypatch.setattr(
        auth_router,
        "create_access_token",
        lambda user_id, role: "test-access-token",
    )
    return FakeDatabase()


def test_refresh_rotates_token(environment):
    initial = Response()
    auth_router._issue_refresh(environment, "user-1", initial)
    old = cookie_value(initial)

    renewed = Response()
    result = auth_router.refresh(
        make_request(old),
        renewed,
        environment,
    )

    new = cookie_value(renewed)

    assert result.access_token == "test-access-token"
    assert old != new
    assert environment.sessions[
        auth_router._hash_refresh(old)
    ]["revoked"]


def test_refresh_replay_rejected(environment):
    initial = Response()
    auth_router._issue_refresh(environment, "user-1", initial)
    token = cookie_value(initial)

    auth_router.refresh(
        make_request(token),
        Response(),
        environment,
    )

    with pytest.raises(HTTPException) as exc:
        auth_router.refresh(
            make_request(token),
            Response(),
            environment,
        )

    assert exc.value.status_code == 401


def test_logout_revokes_session(environment):
    initial = Response()
    auth_router._issue_refresh(environment, "user-1", initial)
    token = cookie_value(initial)

    response = auth_router.logout_session(
        make_request(token),
        Response(),
        environment,
    )

    assert response.status_code == 204

    with pytest.raises(HTTPException) as exc:
        auth_router.refresh(
            make_request(token),
            Response(),
            environment,
        )

    assert exc.value.status_code == 401


def test_expired_session_rejected(environment):
    initial = Response()
    auth_router._issue_refresh(environment, "user-1", initial)
    token = cookie_value(initial)

    environment.sessions[
        auth_router._hash_refresh(token)
    ]["expires"] = datetime.now(timezone.utc) - timedelta(seconds=1)

    with pytest.raises(HTTPException) as exc:
        auth_router.refresh(
            make_request(token),
            Response(),
            environment,
        )

    assert exc.value.status_code == 401


def test_refresh_cookie_security(environment):
    response = Response()
    auth_router._issue_refresh(environment, "user-1", response)

    cookie = response.headers["set-cookie"].lower()

    assert "secure" in cookie
    assert "httponly" in cookie
    assert "samesite=strict" in cookie


def test_missing_refresh_token_rejected(environment):
    with pytest.raises(HTTPException) as exc:
        auth_router.refresh(
            make_request(),
            Response(),
            environment,
        )

    assert exc.value.status_code == 401
