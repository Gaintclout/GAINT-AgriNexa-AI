"""SCIM lease policy boundary tests; no database or worker required."""
from datetime import datetime, timedelta, timezone
import pytest
from pydantic import ValidationError
from app.scim_lease_policy import LeasePolicy, make_lease, lease_expired, can_retry

NOW = datetime(2026, 11, 5, tzinfo=timezone.utc)

def test_default_lease_and_retry_budget():
    policy = LeasePolicy()
    lease = make_lease(NOW, 1, policy)
    assert lease.expires_at == NOW + timedelta(seconds=300)
    assert not lease_expired(lease, lease.expires_at - timedelta(microseconds=1))
    assert lease_expired(lease, lease.expires_at)

@pytest.mark.parametrize("seconds", [0, 29, 901])
def test_reject_lease_duration_outside_bounds(seconds):
    with pytest.raises(ValidationError):
        LeasePolicy(lease_seconds=seconds)

@pytest.mark.parametrize("attempt", [0, 4])
def test_reject_attempt_outside_budget(attempt):
    with pytest.raises(ValueError, match="Attempt outside retry budget"):
        make_lease(NOW, attempt, LeasePolicy())

def test_retry_exhaustion():
    policy = LeasePolicy()
    assert can_retry(0, policy)
    assert can_retry(2, policy)
    assert not can_retry(3, policy)
    assert not can_retry(4, policy)

def test_reject_naive_timestamps():
    with pytest.raises(ValueError, match="timezone"):
        make_lease(NOW.replace(tzinfo=None), 1, LeasePolicy())
    with pytest.raises(ValueError, match="timezone"):
        lease_expired(make_lease(NOW, 1, LeasePolicy()), NOW.replace(tzinfo=None))

def test_reject_negative_attempt_count():
    with pytest.raises(ValueError, match="negative"):
        can_retry(-1, LeasePolicy())
