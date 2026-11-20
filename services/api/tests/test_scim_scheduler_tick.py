"""Unit tests for explicit SCIM scheduler tick."""
import pytest
from unittest.mock import patch
from app.scim_scheduler_tick import run_scheduler_tick

class DummySession:
    def __enter__(self):
        return self
    def __exit__(self, *args):
        return False

def session_factory():
    return DummySession()

def test_recovery_only_does_not_claim():
    with patch("app.scim_scheduler_tick.recover_expired_leases", return_value=(2, 1)) as recover, patch(
        "app.scim_scheduler_tick.claim_with_lease") as claim:
        result = run_scheduler_tick(session_factory, owner="ci-scheduler")
    assert (result.requeued, result.exhausted, result.claim) == (2, 1, None)
    recover.assert_called_once()
    claim.assert_not_called()

def test_optional_claim_occurs_after_recovery():
    calls = []
    def recover(*args, **kwargs):
        calls.append("recover")
        return (1, 0)
    def claim(*args, **kwargs):
        calls.append("claim")
        return ("job-1", "secret-token")
    with patch("app.scim_scheduler_tick.recover_expired_leases", side_effect=recover), patch(
        "app.scim_scheduler_tick.claim_with_lease", side_effect=claim):
        result = run_scheduler_tick(session_factory, owner="ci-scheduler", claim=True)
    assert calls == ["recover", "claim"]
    assert result.claim == ("job-1", "secret-token")

@pytest.mark.parametrize("owner", ["", "  ", "x" * 129])
def test_invalid_owner_rejected(owner):
    with pytest.raises(ValueError, match="owner"):
        run_scheduler_tick(session_factory, owner=owner)

@pytest.mark.parametrize("limit", [0, 101, -1])
def test_invalid_limit_rejected(limit):
    with pytest.raises(ValueError, match="limit"):
        run_scheduler_tick(session_factory, owner="ci-scheduler", recovery_limit=limit)
