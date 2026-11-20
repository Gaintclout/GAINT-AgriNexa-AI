"""Independent SCIM lease heartbeat for long-running offline raster jobs.

A separate database session renews the current fenced token. If renewal fails,
the worker must not report success; the staged worker independently verifies
the token under a database row lock before committing results.
"""
import logging
from threading import Event, Thread
from .scim_lease_policy import LeasePolicy
from .scim_lease_store import renew_lease

LOG = logging.getLogger(__name__)

class LeaseHeartbeat:
    def __init__(self, session_factory, job_id: str, owner: str, token: str,
                 *, policy: LeasePolicy | None = None, interval_seconds: float = 30):
        self.session_factory = session_factory
        self.job_id = job_id
        self.owner = owner
        self.token = token
        self.policy = policy or LeasePolicy()
        if not 1 <= interval_seconds < self.policy.lease_seconds / 2:
            raise ValueError("Heartbeat interval must be less than half the lease")
        self.interval_seconds = interval_seconds
        self._stop = Event()
        self._thread = None
        self.failure = None

    def _run(self):
        while not self._stop.wait(self.interval_seconds):
            try:
                with self.session_factory() as db:
                    renew_lease(db, self.job_id, self.owner, self.token, self.policy)
            except Exception as exc:
                self.failure = exc
                LOG.exception("SCIM lease renewal failed for job %s", self.job_id)
                self._stop.set()
                return

    def __enter__(self):
        self._thread = Thread(target=self._run, name="scim-lease-heartbeat", daemon=True)
        self._thread.start()
        return self

    def __exit__(self, *args):
        self._stop.set()
        self._thread.join(timeout=self.interval_seconds + 5)
        if self._thread.is_alive():
            raise RuntimeError("SCIM lease heartbeat did not terminate")
        if self.failure is not None and args[0] is None:
            raise RuntimeError("SCIM lease heartbeat failed") from self.failure
        return False
