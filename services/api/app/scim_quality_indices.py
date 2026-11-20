"""Combine QA screening with already-calibrated sensor reflectance.

This pure function does not read imagery, locate pixels or establish parcel ownership.
"""
from pydantic import BaseModel, Field, model_validator
from .scim_bands import BAND_MAP, SensorBandSample
from .scim_cloud_mask import PixelQuality, QualitySensor, is_clear_pixel
from .scim_contracts import SatelliteProvider
from .scim_indices import ReflectanceSample, SpectralIndices, calculate_indices

class QualityBandSample(BaseModel):
    provider: SatelliteProvider
    qa_value: int = Field(ge=0, le=65535)
    bands: dict[str, float] = Field(min_length=4, max_length=20)

    @model_validator(mode="after")
    def validate_required_bands(self):
        SensorBandSample(provider=self.provider, bands=self.bands)
        return self

class QualityBandResult(BaseModel):
    clear_pixel: bool
    indices: SpectralIndices | None

def evaluate_quality_bands(sample: QualityBandSample) -> QualityBandResult:
    clear = is_clear_pixel(PixelQuality(
        sensor=QualitySensor(sample.provider.value), qa_value=sample.qa_value))
    if not clear:
        return QualityBandResult(clear_pixel=False, indices=None)
    mapping = BAND_MAP[sample.provider]
    reflectance = ReflectanceSample(**{
        name: sample.bands[band] for name, band in mapping.items()
    })
    return QualityBandResult(clear_pixel=True, indices=calculate_indices(reflectance))
