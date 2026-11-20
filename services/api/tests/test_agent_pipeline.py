"""Internal pipeline security and correctness tests."""

from decimal import Decimal
from unittest.mock import Mock, patch

import pytest
from fastapi import HTTPException
from pydantic import ValidationError

from app.agent_data_access import ParcelContext
from app.agent_pipeline import (
    PipelineRequest,
    prepare_parcel_profile,
)
from app.security import Principal, Role


def actor():
    return Principal(subject="farmer-a", role=Role.farmer)


def context():
    return ParcelContext(
        parcel_id="parcel-1",
        farmer_id="farmer-a",
        village_code="village-1",
        area_hectares=Decimal("1.2500"),
    )


def test_complete_pipeline():
    db = Mock()
    with patch(
        "app.agent_pipeline.load_parcel_context",
        return_value=context(),
    ) as resolver:
        result = prepare_parcel_profile(
            db,
            actor(),
            PipelineRequest(
                parcel_id="parcel-1",
                crop_name="Rice",
                season="Kharif",
            ),
        )

    resolver.assert_called_once()
    assert result.profile.completeness_percent == 100
    assert result.intake.farmer_id == "farmer-a"
    assert result.village_code == "village-1"
    assert result.area_hectares == "1.2500"
    assert result.persisted is False
    db.commit.assert_not_called()


def test_missing_metadata_not_invented():
    with patch(
        "app.agent_pipeline.load_parcel_context",
        return_value=context(),
    ):
        result = prepare_parcel_profile(
            Mock(),
            actor(),
            PipelineRequest(parcel_id="parcel-1"),
        )

    assert result.intake.crop_name is None
    assert result.intake.season is None
    assert result.profile.completeness_percent == 50
    assert result.profile.missing_fields == [
        "crop_name", "season"
    ]


def test_ownership_denial_propagates():
    db = Mock()

    with patch(
        "app.agent_pipeline.load_parcel_context",
        side_effect=HTTPException(
            status_code=404,
            detail="Parcel not found",
        ),
    ):
        with pytest.raises(HTTPException) as exc:
            prepare_parcel_profile(
                db,
                actor(),
                PipelineRequest(parcel_id="parcel-other"),
            )

    assert exc.value.status_code == 404
    db.commit.assert_not_called()


def test_invalid_request_rejected():
    with pytest.raises(ValidationError):
        PipelineRequest(parcel_id="")

    with pytest.raises(ValidationError):
        PipelineRequest(
            parcel_id="parcel-1",
            unexpected="value",
        )


def test_whitespace_normalized():
    with patch(
        "app.agent_pipeline.load_parcel_context",
        return_value=context(),
    ) as resolver:
        result = prepare_parcel_profile(
            Mock(),
            actor(),
            PipelineRequest(
                parcel_id=" parcel-1 ",
                crop_name=" Rice ",
            ),
        )

    assert resolver.call_args.args[2] == "parcel-1"
    assert result.intake.crop_name == "Rice"
