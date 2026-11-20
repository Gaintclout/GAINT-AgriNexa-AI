"""SCIM worker graceful shutdown tests."""
from threading import Event
from unittest.mock import patch
from app.scim_worker_service import run_worker_forever

def test_stopped_worker_does_not_claim(tmp_path):
    stop = Event()
    stop.set()
    with patch("app.scim_worker_service.run_worker_cycle") as cycle:
        run_worker_forever(lambda: None, owner="worker", root=tmp_path,
                           manifest_loader=lambda _: None, stop_event=stop)
    cycle.assert_not_called()

def test_worker_exits_after_one_cycle(tmp_path):
    stop = Event()
    def one_cycle(*args, **kwargs):
        stop.set()
        return {"processed": False, "requeued": 0, "exhausted": 0}
    with patch("app.scim_worker_service.run_worker_cycle", side_effect=one_cycle) as cycle:
        run_worker_forever(lambda: None, owner="worker", root=tmp_path,
                           manifest_loader=lambda _: None, stop_event=stop)
    cycle.assert_called_once()
