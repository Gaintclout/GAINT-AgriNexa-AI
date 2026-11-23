
"""AG-09: Parcel registry API contract and validation tests.

These tests verify registered FastAPI endpoints and Pydantic
request schemas without connecting to PostgreSQL.

They do not perform HTTP authorization or database integration tests.
"""

from decimal import Decimal

import pytest
from pydantic import ValidationError

from app.main import app
from app.registry_router import (
    ParcelInput,
    ParcelUpdateInput,
)


# --------------------------------------------------
# OpenAPI route verification
# --------------------------------------------------

def find_route(path: str, method: str) -> dict:
    """Find an API operation through FastAPI's OpenAPI schema."""

    paths = app.openapi().get("paths", {})
    operations = paths.get(path, {})

    operation = operations.get(method.lower())

    assert operation is not None, (
        f"Expected {method.upper()} {path} "
        "in the OpenAPI schema"
    )

    return operation


def test_parcel_update_route_exists():
    operation = find_route(
        "/api/v1/parcels/{parcel_id}",
        "PATCH",
    )

    assert "200" in operation["responses"]
    assert "422" in operation["responses"]


def test_parcel_owner_route_still_exists():
    find_route(
        "/api/v1/parcels/{parcel_id}/owner",
        "PATCH",
    )


def test_parcel_create_route_still_exists():
    operation = find_route(
        "/api/v1/parcels",
        "POST",
    )

    assert "201" in operation["responses"]


def test_parcel_read_route_still_exists():
    operation = find_route(
        "/api/v1/parcels/{parcel_id}",
        "GET",
    )

    assert "200" in operation["responses"]


# --------------------------------------------------
# Valid parcel updates
# --------------------------------------------------

def test_valid_partial_update():
    payload = ParcelUpdateInput(
        area_hectares=Decimal("2.5000")
    )

    assert payload.model_dump(exclude_unset=True) == {
        "area_hectares": Decimal("2.5000")
    }


def test_multiple_fields_update():
    payload = ParcelUpdateInput(
        external_id="PARCEL-101",
        village_code="VILLAGE-01",
        area_hectares=Decimal("3.2500"),
    )

    assert payload.external_id == "PARCEL-101"
    assert payload.village_code == "VILLAGE-01"
    assert payload.area_hectares == Decimal("3.2500")


def test_identifier_whitespace_trimmed():
    payload = ParcelUpdateInput(
        external_id="  PARCEL-101  ",
        village_code="  VILLAGE-01  ",
    )

    assert payload.external_id == "PARCEL-101"
    assert payload.village_code == "VILLAGE-01"


def test_partial_update_does_not_include_other_fields():
    payload = ParcelUpdateInput(
        area_hectares=Decimal("4.2500")
    )

    changes = payload.model_dump(exclude_unset=True)

    assert set(changes) == {"area_hectares"}
    assert "external_id" not in changes
    assert "village_code" not in changes


# --------------------------------------------------
# Invalid area validation
# --------------------------------------------------

@pytest.mark.parametrize(
    "area",
    [
        Decimal("0"),
        Decimal("-1"),
        Decimal("1.12345"),
        Decimal("100000000"),
    ],
)
def test_invalid_area_rejected(area):
    with pytest.raises(ValidationError):
        ParcelUpdateInput(
            area_hectares=area
        )


# --------------------------------------------------
# Invalid parcel identifiers
# --------------------------------------------------

@pytest.mark.parametrize(
    "value",
    [
        "",
        "   ",
        "X" * 101,
    ],
)
def test_invalid_external_id_rejected(value):
    with pytest.raises(ValidationError):
        ParcelUpdateInput(
            external_id=value
        )


@pytest.mark.parametrize(
    "value",
    [
        "",
        "   ",
        "V" * 101,
    ],
)
def test_invalid_village_code_rejected(value):
    with pytest.raises(ValidationError):
        ParcelUpdateInput(
            village_code=value
        )


# --------------------------------------------------
# Explicit null and empty update contracts
# --------------------------------------------------

@pytest.mark.parametrize(
    "field",
    [
        "external_id",
        "village_code",
        "area_hectares",
    ],
)
def test_explicit_null_is_detectable(field):
    """The endpoint rejects explicit null after schema parsing."""

    payload = ParcelUpdateInput.model_validate({
        field: None
    })

    changes = payload.model_dump(exclude_unset=True)

    assert field in changes
    assert changes[field] is None


def test_empty_update_produces_no_changes():
    """The endpoint must reject this empty change set."""

    payload = ParcelUpdateInput()

    assert payload.model_dump(exclude_unset=True) == {}


# --------------------------------------------------
# Protected fields
# --------------------------------------------------

def test_owner_cannot_be_updated_through_general_schema():
    payload = ParcelUpdateInput.model_validate({
        "external_id": "PARCEL-101",
        "farmer_id": "different-owner",
    })

    assert "farmer_id" not in payload.model_dump()


def test_created_at_cannot_be_updated_through_general_schema():
    payload = ParcelUpdateInput.model_validate({
        "area_hectares": "2.5",
        "created_at": "2026-01-01T00:00:00Z",
    })

    assert "created_at" not in payload.model_dump()


def test_geometry_cannot_be_updated_through_general_schema():
    payload = ParcelUpdateInput.model_validate({
        "area_hectares": "2.5",
        "geom": "INVALID",
    })

    assert "geom" not in payload.model_dump()


def test_record_id_cannot_be_updated_through_general_schema():
    payload = ParcelUpdateInput.model_validate({
        "external_id": "PARCEL-101",
        "id": "different-record-id",
    })

    assert "id" not in payload.model_dump()


# --------------------------------------------------
# Parcel creation regression
# --------------------------------------------------

def test_creation_schema_still_accepts_valid_parcel():
    payload = ParcelInput(
        external_id="PARCEL-001",
        village_code="VILLAGE-01",
        area_hectares=Decimal("2.5000"),
    )

    assert payload.external_id == "PARCEL-001"
    assert payload.farmer_id is None


def test_creation_rejects_zero_area():
    with pytest.raises(ValidationError):
        ParcelInput(
            external_id="PARCEL-001",
            village_code="VILLAGE-01",
            area_hectares=Decimal("0"),
        )


def test_creation_trims_identifiers():
    payload = ParcelInput(
        external_id="  PARCEL-001  ",
        village_code="  VILLAGE-01  ",
        area_hectares=Decimal("2.5000"),
    )

    assert payload.external_id == "PARCEL-001"
    assert payload.village_code == "VILLAGE-01"
