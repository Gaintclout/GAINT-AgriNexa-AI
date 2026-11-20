from unittest.mock import Mock, patch

import pytest
from fastapi import HTTPException

from app.crop_advisory_agent import CropAdvisoryRequest
from app.crop_advisory_router import generate_advisory


class Principal:
    subject = "test-user"
    role = Mock(value="admin")


class ActiveUser:
    is_active = True
    role = "admin"


def make_request(**kwargs):
    values = {
        "crop_name": "rice",
        "growth_stage": "vegetative",
    }
    values.update(kwargs)
    return CropAdvisoryRequest(**values)


def test_inactive_account_denied():
    db = Mock()
    db.get.return_value = None

    with pytest.raises(HTTPException) as exc:
        generate_advisory(
            make_request(),
            Principal(),
            db,
        )

    assert exc.value.status_code == 401


def test_role_mismatch_denied():
    db = Mock()
    user = ActiveUser()
    user.role = "farmer"
    db.get.return_value = user

    with pytest.raises(HTTPException) as exc:
        generate_advisory(
            make_request(),
            Principal(),
            db,
        )

    assert exc.value.status_code == 401


def test_authorized_advisory():
    db = Mock()
    db.get.return_value = ActiveUser()

    with patch(
        "app.crop_advisory_router.generate_crop_advisory"
    ) as engine:
        engine.return_value = {"advisory_only": True}

        result = generate_advisory(
            make_request(),
            Principal(),
            db,
        )

    assert result["advisory_only"] is True
    engine.assert_called_once()


def test_invalid_weather_request_returns_422():
    db = Mock()
    db.get.return_value = ActiveUser()

    with pytest.raises(HTTPException) as exc:
        generate_advisory(
            make_request(include_weather=True),
            Principal(),
            db,
        )

    assert exc.value.status_code == 422
