from unittest.mock import Mock, patch

import pytest
from fastapi import HTTPException

from app.scheme_agent import SchemeDataError, SchemeRequest
from app.scheme_agent_router import screen_schemes

class Principal:
    subject = "test-user"
    role = Mock(value="admin")

class ActiveUser:
    is_active = True
    role = "admin"

def test_missing_account_denied():
    db = Mock()
    db.get.return_value = None
    with pytest.raises(HTTPException) as exc:
        screen_schemes(SchemeRequest(), Principal(), db)
    assert exc.value.status_code == 401

def test_inactive_account_denied():
    db = Mock()
    user = ActiveUser()
    user.is_active = False
    db.get.return_value = user
    with pytest.raises(HTTPException) as exc:
        screen_schemes(SchemeRequest(), Principal(), db)
    assert exc.value.status_code == 401

def test_role_mismatch_denied():
    db = Mock()
    user = ActiveUser()
    user.role = "farmer"
    db.get.return_value = user
    with pytest.raises(HTTPException) as exc:
        screen_schemes(SchemeRequest(), Principal(), db)
    assert exc.value.status_code == 401

def test_authorized_screening():
    db = Mock()
    db.get.return_value = ActiveUser()
    with patch(
        "app.scheme_agent_router.generate_scheme_guidance",
        return_value={"available": False},
    ) as engine:
        result = screen_schemes(SchemeRequest(), Principal(), db)
    assert result["available"] is False
    engine.assert_called_once()

def test_invalid_catalogue_returns_503():
    db = Mock()
    db.get.return_value = ActiveUser()
    with patch(
        "app.scheme_agent_router.generate_scheme_guidance",
        side_effect=SchemeDataError("invalid"),
    ):
        with pytest.raises(HTTPException) as exc:
            screen_schemes(SchemeRequest(), Principal(), db)
    assert exc.value.status_code == 503
