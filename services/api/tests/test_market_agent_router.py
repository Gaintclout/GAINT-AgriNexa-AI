from unittest.mock import Mock, patch

import pytest
from fastapi import HTTPException

from app.market_agent import (
    MarketDataError,
    MarketRequest,
)
from app.market_agent_router import market_prices


class Principal:
    subject = "test-user"
    role = Mock(value="admin")


class ActiveUser:
    is_active = True
    role = "admin"


def request():
    return MarketRequest(commodity="rice")


def test_missing_account_denied():
    db = Mock()
    db.get.return_value = None

    with pytest.raises(HTTPException) as exc:
        market_prices(request(), Principal(), db)

    assert exc.value.status_code == 401


def test_inactive_account_denied():
    db = Mock()
    user = ActiveUser()
    user.is_active = False
    db.get.return_value = user

    with pytest.raises(HTTPException) as exc:
        market_prices(request(), Principal(), db)

    assert exc.value.status_code == 401


def test_role_mismatch_denied():
    db = Mock()
    user = ActiveUser()
    user.role = "farmer"
    db.get.return_value = user

    with pytest.raises(HTTPException) as exc:
        market_prices(request(), Principal(), db)

    assert exc.value.status_code == 401


def test_authorized_market_request():
    db = Mock()
    db.get.return_value = ActiveUser()

    with patch(
        "app.market_agent_router.generate_market_intelligence",
        return_value={"available": False},
    ) as engine:
        result = market_prices(
            request(),
            Principal(),
            db,
        )

    assert result["available"] is False
    engine.assert_called_once()


def test_invalid_market_data_returns_503():
    db = Mock()
    db.get.return_value = ActiveUser()

    with patch(
        "app.market_agent_router.generate_market_intelligence",
        side_effect=MarketDataError("invalid"),
    ):
        with pytest.raises(HTTPException) as exc:
            market_prices(
                request(),
                Principal(),
                db,
            )

    assert exc.value.status_code == 503
