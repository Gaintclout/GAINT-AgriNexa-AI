"""Unit tests for sensor-specific SCIM cloud masking."""
import pytest
from pydantic import ValidationError
from app.scim_cloud_mask import PixelQuality, QualitySensor, is_clear_pixel

@pytest.mark.parametrize("code,clear", [
    (0, False), (1, False), (2, False), (3, False),
    (4, True), (5, True), (6, True), (7, False),
    (8, False), (9, False), (10, False), (11, False),
])
def test_sentinel_scl(code, clear):
    assert is_clear_pixel(PixelQuality(sensor=QualitySensor.sentinel_2, qa_value=code)) is clear

@pytest.mark.parametrize("bit", range(6))
def test_landsat_rejects_bad_flags(bit):
    assert not is_clear_pixel(PixelQuality(sensor=QualitySensor.landsat_8, qa_value=1 << bit))

@pytest.mark.parametrize("sensor", [QualitySensor.landsat_8, QualitySensor.landsat_9])
def test_landsat_accepts_clear_and_water(sensor):
    assert is_clear_pixel(PixelQuality(sensor=sensor, qa_value=0))
    assert is_clear_pixel(PixelQuality(sensor=sensor, qa_value=(1 << 6) | (1 << 7)))

def test_qa_bounds():
    with pytest.raises(ValidationError):
        PixelQuality(sensor=QualitySensor.landsat_9, qa_value=-1)
    with pytest.raises(ValidationError):
        PixelQuality(sensor=QualitySensor.landsat_9, qa_value=65536)
