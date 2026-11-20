"""SCIM raw-pixel pipeline tests."""
import pytest
from pydantic import ValidationError
from app.scim_raw_pixel import RawPixelInput, evaluate_raw_pixel

LANDSAT = {"SR_B4": 10000, "SR_B5": 20000, "SR_B3": 15000, "SR_B6": 12000}
SENTINEL = {"B04": 2000, "B08": 6000, "B03": 3000, "B11": 4000}

def test_clear_landsat_pipeline():
    result = evaluate_raw_pixel(RawPixelInput(
        provider="landsat-8", qa_value=64,
        calibration={"provider": "landsat-8", "digital_numbers": LANDSAT}))
    assert result.clear_pixel
    assert result.indices.ndvi == pytest.approx(0.647059, abs=1e-6)

def test_cloud_mask_skips_calibration():
    result = evaluate_raw_pixel(RawPixelInput(
        provider="landsat-9", qa_value=8,
        calibration={"provider": "landsat-9",
                     "digital_numbers": {**LANDSAT, "SR_B4": 0}}))
    assert not result.clear_pixel
    assert result.indices is None

def test_sentinel_metadata_pipeline():
    result = evaluate_raw_pixel(RawPixelInput(
        provider="sentinel-2", qa_value=4,
        calibration={"provider": "sentinel-2", "digital_numbers": SENTINEL,
                     "sentinel_quantification": 10000,
                     "sentinel_offsets": {band: -1000 for band in SENTINEL}}))
    assert result.clear_pixel and result.indices.ndvi == pytest.approx(0.666667, abs=1e-6)

def test_sensor_mismatch_rejected():
    with pytest.raises(ValidationError):
        RawPixelInput(provider="landsat-9", qa_value=64,
                      calibration={"provider": "landsat-8", "digital_numbers": LANDSAT})
