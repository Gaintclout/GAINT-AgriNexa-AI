"""Tests for co-registered bounded SCIM raster grids."""
import pytest
from pydantic import ValidationError
from app.scim_raster_grid import RasterEvaluationRequest, evaluate_raster_grid

def grid(values, crs="EPSG:32644"):
    return {"width": 2, "height": 1, "crs": crs,
            "transform": [10, 0, 500000, 0, -10, 1900000], "values": values}

def request():
    return {
        "provider": "landsat-8",
        "qa": grid([64, 8]),
        "bands": {
            "SR_B4": grid([10000, 10000]),
            "SR_B5": grid([20000, 20000]),
            "SR_B3": grid([15000, 15000]),
            "SR_B6": grid([12000, 12000]),
        },
        "parcel_mask": [True, True],
    }

def test_clear_and_cloudy_pixels():
    result = evaluate_raster_grid(RasterEvaluationRequest(**request()))
    assert (result.parcel_pixels, result.clear_pixels, result.valid_pixels) == (2, 1, 1)
    assert result.ndvi_values == [pytest.approx(0.647059, abs=1e-6)]

def test_outside_parcel_excluded():
    payload = request()
    payload["parcel_mask"] = [False, True]
    result = evaluate_raster_grid(RasterEvaluationRequest(**payload))
    assert (result.parcel_pixels, result.clear_pixels, result.valid_pixels) == (1, 0, 0)

def test_misaligned_crs_rejected():
    payload = request()
    payload["bands"]["SR_B4"] = grid([10000, 10000], crs="EPSG:4326")
    with pytest.raises(ValidationError, match="co-registered"):
        RasterEvaluationRequest(**payload)

def test_mask_size_rejected():
    payload = request()
    payload["parcel_mask"] = [True]
    with pytest.raises(ValidationError, match="mask size"):
        RasterEvaluationRequest(**payload)

def test_invalid_dn_rejected():
    payload = request()
    payload["bands"]["SR_B4"] = grid([70000, 10000])
    with pytest.raises(ValidationError, match="uint16"):
        RasterEvaluationRequest(**payload)
