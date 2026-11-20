"""Tests for QA-gated spectral index calculations."""
import pytest
from pydantic import ValidationError
from app.scim_quality_indices import QualityBandSample, evaluate_quality_bands

SENTINEL = {"B04": 0.2, "B08": 0.6, "B03": 0.3, "B11": 0.4}
LANDSAT = {"SR_B4": 0.2, "SR_B5": 0.6, "SR_B3": 0.3, "SR_B6": 0.4}

def test_clear_sentinel_indices():
    result = evaluate_quality_bands(QualityBandSample(
        provider="sentinel-2", qa_value=4, bands=SENTINEL))
    assert result.clear_pixel
    assert result.indices.ndvi == 0.5
    assert result.indices.ndmi == 0.2

def test_cloudy_sentinel_skips_calculation():
    result = evaluate_quality_bands(QualityBandSample(
        provider="sentinel-2", qa_value=9, bands=SENTINEL))
    assert not result.clear_pixel
    assert result.indices is None

@pytest.mark.parametrize("provider", ["landsat-8", "landsat-9"])
def test_landsat_clear_and_cloud(provider):
    clear = evaluate_quality_bands(QualityBandSample(
        provider=provider, qa_value=1 << 6, bands=LANDSAT))
    assert clear.clear_pixel and clear.indices.ndvi == 0.5
    cloud = evaluate_quality_bands(QualityBandSample(
        provider=provider, qa_value=1 << 3, bands=LANDSAT))
    assert not cloud.clear_pixel and cloud.indices is None

def test_clear_invalid_reflectance_fails_closed():
    with pytest.raises(ValidationError):
        evaluate_quality_bands(QualityBandSample(
            provider="sentinel-2", qa_value=4, bands={**SENTINEL, "B08": 1.2}))

def test_missing_sensor_band_rejected():
    with pytest.raises(ValidationError):
        QualityBandSample(provider="sentinel-2", qa_value=4,
                          bands={"B04": 0.2, "B08": 0.6, "B03": 0.3, "other": 0.4})
