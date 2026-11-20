"""Tests for raw satellite reflectance calibration."""
import pytest
from pydantic import ValidationError
from app.scim_calibration import CalibrationInput, calibrate_reflectance

LANDSAT = {"SR_B4": 10000, "SR_B5": 20000, "SR_B3": 15000, "SR_B6": 12000}
SENTINEL = {"B04": 2000, "B08": 6000, "B03": 3000, "B11": 4000}

@pytest.mark.parametrize("provider", ["landsat-8", "landsat-9"])
def test_landsat_collection_two_calibration(provider):
    result = calibrate_reflectance(CalibrationInput(provider=provider, digital_numbers=LANDSAT))
    assert result.red == pytest.approx(0.075)
    assert result.nir == pytest.approx(0.35)

def test_sentinel_metadata_calibration():
    result = calibrate_reflectance(CalibrationInput(
        provider="sentinel-2", digital_numbers=SENTINEL,
        sentinel_quantification=10000,
        sentinel_offsets={band: -1000 for band in SENTINEL}))
    assert result.red == pytest.approx(0.1)
    assert result.nir == pytest.approx(0.5)

def test_sentinel_requires_offsets():
    with pytest.raises(ValidationError):
        CalibrationInput(provider="sentinel-2", digital_numbers=SENTINEL,
                         sentinel_quantification=10000)

def test_nodata_rejected():
    with pytest.raises(ValueError, match="No-data"):
        calibrate_reflectance(CalibrationInput(
            provider="landsat-8", digital_numbers={**LANDSAT, "SR_B4": 0}))

def test_out_of_range_reflectance_rejected():
    with pytest.raises(ValidationError):
        calibrate_reflectance(CalibrationInput(
            provider="landsat-8", digital_numbers={**LANDSAT, "SR_B4": 1}))
