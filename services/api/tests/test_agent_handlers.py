"""Unit tests for deterministic INTAKE and PROFILE handlers."""

import pytest
from pydantic import ValidationError

from app.agent_handlers import (
    IntakeInput,
    build_profile,
    process_intake,
)


def test_intake_valid_record():
    data = IntakeInput(
        farmer_id="farmer-1",
        parcel_id="parcel-1",
        crop_name="Rice",
        season="Kharif",
    )
    result = process_intake(data)
    assert result.status == "validated"
    assert result.crop_name == "Rice"


def test_intake_trims_whitespace():
    data = IntakeInput(
        farmer_id=" farmer-1 ",
        parcel_id=" parcel-1 ",
        crop_name=" Rice ",
    )
    result = process_intake(data)
    assert result.farmer_id == "farmer-1"
    assert result.parcel_id == "parcel-1"
    assert result.crop_name == "Rice"


@pytest.mark.parametrize("field", ["farmer_id", "parcel_id"])
def test_required_identifiers_reject_blanks(field):
    values = {"farmer_id": "farmer-1", "parcel_id": "parcel-1"}
    values[field] = "   "
    with pytest.raises(ValidationError):
        IntakeInput(**values)


def test_extra_fields_rejected():
    with pytest.raises(ValidationError):
        IntakeInput(
            farmer_id="farmer-1",
            parcel_id="parcel-1",
            unexpected="value",
        )


def test_complete_profile():
    intake = process_intake(IntakeInput(
        farmer_id="farmer-1",
        parcel_id="parcel-1",
        crop_name="Rice",
        season="Kharif",
    ))
    result = build_profile(intake)
    assert result.status == "complete"
    assert result.completeness_percent == 100
    assert result.missing_fields == []


def test_incomplete_profile():
    intake = process_intake(IntakeInput(
        farmer_id="farmer-1",
        parcel_id="parcel-1",
    ))
    result = build_profile(intake)
    assert result.status == "incomplete"
    assert result.completeness_percent == 50
    assert result.missing_fields == ["crop_name", "season"]


def test_blank_optional_values_are_missing():
    intake = process_intake(IntakeInput(
        farmer_id="farmer-1",
        parcel_id="parcel-1",
        crop_name=" ",
        season=" ",
    ))
    result = build_profile(intake)
    assert result.completeness_percent == 50


def test_input_is_not_mutated():
    data = IntakeInput(
        farmer_id="farmer-1",
        parcel_id="parcel-1",
        crop_name="Rice",
    )
    before = data.model_dump()
    process_intake(data)
    assert data.model_dump() == before
