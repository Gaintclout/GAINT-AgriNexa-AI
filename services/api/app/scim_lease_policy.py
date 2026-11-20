"""Fail-closed SCIM retry and lease policy. No scheduler or worker is enabled."""
from datetime import datetime, timedelta, timezone
from pydantic import BaseModel, Field, model_validator

MAX_ATTEMPTS = 3
MIN_LEASE_SECONDS = 30
MAX_LEASE_SECONDS = 900

class LeasePolicy(BaseModel):
    lease_seconds: int = Field(default=300, ge=MIN_LEASE_SECONDS, le=MAX_LEASE_SECONDS)
    max_attempts: int = Field(default=MAX_ATTEMPTS, ge=1, le=MAX_ATTEMPTS)

class LeaseSnapshot(BaseModel):
    attempt: int = Field(ge=1)
    claimed_at: datetime
    expires_at: datetime

    @model_validator(mode="after")
    def validate_lease(self):
        if any(dt.tzinfo is None or dt.utcoffset() is None
               for dt in (self.claimed_at, self.expires_at)):
            raise ValueError("Lease timestamps must include timezone")
        if self.expires_at <= self.claimed_at:
            raise ValueError("Lease must expire after claim")
        return self

def make_lease(at: datetime, attempt: int, policy: LeasePolicy) -> LeaseSnapshot:
    if at.tzinfo is None or at.utcoffset() is None:
        raise ValueError("Claim timestamp requires timezone")
    if attempt < 1 or attempt > policy.max_attempts:
        raise ValueError("Attempt outside retry budget")
    return LeaseSnapshot(attempt=attempt, claimed_at=at,
                         expires_at=at + timedelta(seconds=policy.lease_seconds))

def lease_expired(lease: LeaseSnapshot, at: datetime) -> bool:
    if at.tzinfo is None or at.utcoffset() is None:
        raise ValueError("Check timestamp requires timezone")
    return at.astimezone(timezone.utc) >= lease.expires_at.astimezone(timezone.utc)

def can_retry(attempts_used: int, policy: LeasePolicy) -> bool:
    if attempts_used < 0:
        raise ValueError("Attempts cannot be negative")
    return attempts_used < policy.max_attempts
