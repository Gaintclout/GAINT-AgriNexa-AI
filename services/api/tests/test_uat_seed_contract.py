from types import SimpleNamespace

import pytest
from app.security import Role
from tools import seed_uat_browser_data as seed


class FakeSession:
    def __init__(self, user=None):
        self.user = user
        self.added = []
        self.flush_count = 0

    def scalar(self, _query):
        return self.user

    def add(self, user):
        self.added.append(user)
        self.user = user

    def flush(self):
        self.flush_count += 1


def test_uat_seed_accounts_cover_every_application_role():
    assert {role for _, _, role in seed.ACCOUNTS} == set(Role)
    assert len({email for _, email, _ in seed.ACCOUNTS}) == len(seed.ACCOUNTS)


def test_uat_seed_never_changes_existing_account_password(monkeypatch):
    user = SimpleNamespace(role=Role.farmer.value, is_active=True, password_hash="old-hash")
    db = FakeSession(user)
    monkeypatch.setattr(seed, "verify_password", lambda _password, _stored: False)
    monkeypatch.setattr(seed, "hash_password", lambda _password: pytest.fail("must not change an existing password"))
    credentials = {"accounts": {"farmer_a": {"password": "new-uat-password"}}}

    with pytest.raises(RuntimeError, match="password does not match"):
        seed.ensure_account(db, "farmer_a", "farmer.a.uat@agrinexa.example", Role.farmer, credentials)
    assert user.password_hash == "old-hash"
    assert db.flush_count == 0


def test_uat_seed_rejects_existing_account_with_wrong_role_before_password_change(monkeypatch):
    user = SimpleNamespace(role=Role.officer.value, is_active=True, password_hash="unchanged")
    db = FakeSession(user)
    monkeypatch.setattr(seed, "hash_password", lambda _password: pytest.fail("must not change unexpected account"))
    credentials = {"accounts": {"farmer_a": {"password": "new-uat-password"}}}

    with pytest.raises(RuntimeError, match="unexpected state"):
        seed.ensure_account(db, "farmer_a", "farmer.a.uat@agrinexa.example", Role.farmer, credentials)
    assert user.password_hash == "unchanged"
    assert db.flush_count == 0
