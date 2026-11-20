"""Deterministic SCIM heartbeat tests without database or sleeping."""
from unittest.mock import patch
import pytest
from app.scim_lease_heartbeat import LeaseHeartbeat

class Session:
    def __enter__(self):
        return self
    def __exit__(self, *args):
        return False

def factory():
    return Session()

def test_heartbeat_renews_current_fenced_token():
    heartbeat = LeaseHeartbeat(factory, "job-1", "worker-a", "token-a")
    count = 0
    def wait(_):
        nonlocal count
        count += 1
        return count > 1
    with patch.object(heartbeat._stop, "wait", side_effect=wait), patch(
        "app.scim_lease_heartbeat.renew_lease") as renew:
        heartbeat._run()
    renew.assert_called_once()
    assert renew.call_args.args[1:4] == ("job-1", "worker-a", "token-a")
    assert heartbeat.failure is None

def test_heartbeat_stops_on_renewal_failure():
    heartbeat = LeaseHeartbeat(factory, "job-1", "worker-a", "token-a")
    with patch.object(heartbeat._stop, "wait", return_value=False), patch(
        "app.scim_lease_heartbeat.renew_lease", side_effect=ValueError("stale")):
        heartbeat._run()
    assert isinstance(heartbeat.failure, ValueError)
    assert heartbeat._stop.is_set()

@pytest.mark.parametrize("interval", [0, 150, 300])
def test_unsafe_heartbeat_interval_rejected(interval):
    with pytest.raises(ValueError, match="interval"):
        LeaseHeartbeat(factory, "job-1", "worker-a", "token-a",
                       interval_seconds=interval)

def test_heartbeat_context_terminates():
    with LeaseHeartbeat(factory, "job-1", "worker-a", "token-a") as heartbeat:
        assert heartbeat._thread.is_alive()
    assert not heartbeat._thread.is_alive()
