"""Security tests for read-only parcel context resolution."""

from decimal import Decimal
from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from app.agent_data_access import load_parcel_context
from app.models import Parcel, User
from app.security import Principal, Role


class FakeDB:
    def __init__(
        self,
        *,
        actor_role="farmer",
        actor_active=True,
        actor_exists=True,
        parcel_exists=True,
        owner="farmer-a",
        farmer_active=True,
        farmer_role="farmer",
        farmer_exists=True,
    ):
        self.actor_role = actor_role
        self.actor_active = actor_active
        self.actor_exists = actor_exists
        self.parcel_exists = parcel_exists
        self.owner = owner
        self.farmer_active = farmer_active
        self.farmer_role = farmer_role
        self.farmer_exists = farmer_exists
        self.calls = []

    def get(self, model, identifier):
        self.calls.append((model, identifier))

        if model is Parcel:
            if not self.parcel_exists:
                return None
            return SimpleNamespace(
                id="parcel-1",
                farmer_id=self.owner,
                village_code="village-1",
                area_hectares=Decimal("1.2500"),
            )

        if model is User:
            if identifier == "admin-1":
                return SimpleNamespace(
                    id=identifier,
                    role=self.actor_role,
                    is_active=self.actor_active,
                ) if self.actor_exists else None

            if identifier == "farmer-a":
                return SimpleNamespace(
                    id=identifier,
                    role=self.actor_role,
                    is_active=self.actor_active,
                ) if self.actor_exists else None

            if identifier == "farmer-b":
                return SimpleNamespace(
                    id=identifier,
                    role="farmer",
                    is_active=True,
                )

            if identifier == "officer-1":
                return SimpleNamespace(
                    id=identifier,
                    role="officer",
                    is_active=True,
                )

            if identifier == "assigned-farmer":
                return SimpleNamespace(
                    id=identifier,
                    role=self.farmer_role,
                    is_active=self.farmer_active,
                ) if self.farmer_exists else None

        return None


def principal(subject, role):
    return Principal(subject=subject, role=role)


def assert_http_error(expected, action):
    with pytest.raises(HTTPException) as exc:
        action()
    assert exc.value.status_code == expected


def test_farmer_can_read_own_parcel():
    db = FakeDB()
    result = load_parcel_context(
        db, principal("farmer-a", Role.farmer), "parcel-1"
    )
    assert result.farmer_id == "farmer-a"
    assert result.area_hectares == Decimal("1.2500")


def test_farmer_cannot_read_other_farmers_parcel():
    db = FakeDB()
    assert_http_error(
        404,
        lambda: load_parcel_context(
            db, principal("farmer-b", Role.farmer), "parcel-1"
        ),
    )


def test_missing_parcel_returns_404():
    db = FakeDB(parcel_exists=False)
    assert_http_error(
        404,
        lambda: load_parcel_context(
            db, principal("farmer-a", Role.farmer), "parcel-1"
        ),
    )


def test_unassigned_parcel_rejected():
    db = FakeDB(owner=None, actor_role="admin")
    assert_http_error(
        409,
        lambda: load_parcel_context(
            db, principal("admin-1", Role.admin), "parcel-1"
        ),
    )


def test_inactive_actor_rejected():
    db = FakeDB(actor_active=False)
    assert_http_error(
        401,
        lambda: load_parcel_context(
            db, principal("farmer-a", Role.farmer), "parcel-1"
        ),
    )


def test_deleted_actor_rejected():
    db = FakeDB(actor_exists=False)
    assert_http_error(
        401,
        lambda: load_parcel_context(
            db, principal("farmer-a", Role.farmer), "parcel-1"
        ),
    )


def test_actor_role_mismatch_rejected():
    db = FakeDB(actor_role="admin")
    assert_http_error(
        401,
        lambda: load_parcel_context(
            db, principal("farmer-a", Role.farmer), "parcel-1"
        ),
    )


def test_unauthorized_role_rejected_before_database_access():
    db = FakeDB()
    assert_http_error(
        403,
        lambda: load_parcel_context(
            db, principal("officer-1", Role.officer), "parcel-1"
        ),
    )
    assert db.calls == []


def test_admin_can_read_assigned_parcel():
    db = FakeDB(owner="assigned-farmer", actor_role="admin")
    result = load_parcel_context(
        db, principal("admin-1", Role.admin), "parcel-1"
    )
    assert result.farmer_id == "assigned-farmer"


def test_inactive_assigned_farmer_rejected():
    db = FakeDB(
        owner="assigned-farmer",
        actor_role="admin",
        farmer_active=False,
    )
    assert_http_error(
        409,
        lambda: load_parcel_context(
            db, principal("admin-1", Role.admin), "parcel-1"
        ),
    )


def test_non_farmer_owner_rejected():
    db = FakeDB(
        owner="assigned-farmer",
        actor_role="admin",
        farmer_role="officer",
    )
    assert_http_error(
        409,
        lambda: load_parcel_context(
            db, principal("admin-1", Role.admin), "parcel-1"
        ),
    )


def test_deleted_assigned_farmer_rejected():
    db = FakeDB(
        owner="assigned-farmer",
        actor_role="admin",
        farmer_exists=False,
    )
    assert_http_error(
        409,
        lambda: load_parcel_context(
            db, principal("admin-1", Role.admin), "parcel-1"
        ),
    )
