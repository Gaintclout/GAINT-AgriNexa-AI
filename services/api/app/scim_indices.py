"""SCIM spectral indices from already-calibrated surface reflectance samples.

These calculations are per sample; no satellite imagery is downloaded or processed.
"""
from math import isfinite
from pydantic import BaseModel, Field, field_validator

class ReflectanceSample(BaseModel):
    red: float = Field(ge=0, le=1)
    nir: float = Field(ge=0, le=1)
    green: float = Field(ge=0, le=1)
    swir1: float = Field(ge=0, le=1)

    @field_validator("red", "nir", "green", "swir1")
    @classmethod
    def finite_reflectance(cls, value: float) -> float:
        if not isfinite(value):
            raise ValueError("Reflectance must be finite")
        return value

class SpectralIndices(BaseModel):
    ndvi: float | None
    ndwi: float | None
    ndmi: float | None

def normalized_difference(a: float, b: float) -> float | None:
    denominator = a + b
    if denominator == 0:
        return None
    return round((a - b) / denominator, 6)

def calculate_indices(sample: ReflectanceSample) -> SpectralIndices:
    return SpectralIndices(
        ndvi=normalized_difference(sample.nir, sample.red),
        ndwi=normalized_difference(sample.green, sample.nir),
        ndmi=normalized_difference(sample.nir, sample.swir1),
    )
