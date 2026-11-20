"""Explicit SCIM scheduler tick for a trusted external scheduler.

This module does not launch a daemon or process imagery. Each invocation
recovers expired leases, then optionally claims one queued job. The returned
lease token must be kept secret and passed only to the trusted worker.
"""
from dataclasses import dataclass
from sqlalchemy.orm import Session
from .scim_lease_policy import LeasePolicy
from .scim_lease_recovery import recover_expired_leases
from .scim_lease_store import claim_with_lease

@dataclass(frozen=True)
class SchedulerTick:
    requeued: int
    exhausted: int
    claim: tuple[str, str] | None

def run_scheduler_tick(session_factory, *, owner: str, claim: bool = False,
                       policy: LeasePolicy | None = None,
                       recovery_limit: int = 50) -> SchedulerTick:
    """Execute one bounded tick; no automatic worker dispatch."""
    if not isinstance(owner, str) or not owner.strip() or len(owner) > 128:
        raise ValueError("Invalid scheduler owner")
    if not isinstance(recovery_limit, int) or not 1 <= recovery_limit <= 100:
        raise ValueError("Recovery limit must be between 1 and 100")
    policy = policy or LeasePolicy()
    with session_factory() as db:
        requeued, exhausted = recover_expired_leases(
            db, policy=policy, limit=recovery_limit)
    selected = None
    if claim:
        with session_factory() as db:
            selected = claim_with_lease(db, owner.strip(), policy=policy)
    return SchedulerTick(requeued=requeued, exhausted=exhausted, claim=selected)
