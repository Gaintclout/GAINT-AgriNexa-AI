"""SCIM worker fencing and summary unit tests."""
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
import pytest
from app.scim_staged_worker import _verify_lease, _summary

def lease(**overrides):
    state = dict(status="running", lease_owner="worker-a",
                 lease_token="token-a",
                 lease_expires_at=datetime.now(timezone.utc) + timedelta(minutes=2))
    state.update(overrides)
    return SimpleNamespace(**state)

def test_valid_lease():
    _verify_lease(lease(), "worker-a", "token-a", datetime.now(timezone.utc))

@pytest.mark.parametrize("changes,owner,token", [
    ({"status": "queued"}, "worker-a", "token-a"),
    ({}, "worker-b", "token-a"),
    ({}, "worker-a", "wrong"),
    ({"lease_expires_at": datetime(2000, 1, 1, tzinfo=timezone.utc)}, "worker-a", "token-a"),
    ({"lease_token": None}, "worker-a", "token-a"),
])
def test_invalid_leases(changes, owner, token):
    with pytest.raises(ValueError, match="lease"):
        _verify_lease(lease(**changes), owner, token, datetime.now(timezone.utc))

def test_result_medians():
    result = SimpleNamespace(parcel_pixels=3, clear_pixels=2, valid_pixels=2,
        ndvi_values=[0.2, 0.8], ndwi_values=[0.1, 0.3], ndmi_values=[-0.2, 0.2])
    summary = _summary(result)
    assert summary["ndvi_median"] == 0.5
    assert summary["ndmi_median"] == 0.0
    assert summary["valid_pixels"] == 2
