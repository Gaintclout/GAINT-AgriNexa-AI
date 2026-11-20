"""Sensor DN-to-reflectance calibration for SCIM pixel samples.

Landsat Collection 2 Level-2 SR: reflectance = DN * 0.0000275 - 0.2.
Sentinel-2 L2A requires metadata-derived offsets and quantification.
These functions do not retrieve rasters or metadata.
"""
from math import isfinite
from pydantic import BaseModel, Field, model_validator
from .scim_bands import BAND_MAP
from .scim_contracts import SatelliteProvider
from .scim_indices import ReflectanceSample

class CalibrationInput(BaseModel):
    provider: SatelliteProvider
    digital_numbers: dict[str, int] = Field(min_length=4, max_length=20)
    sentinel_quantification: float | None = Field(default=None, gt=0)
    sentinel_offsets: dict[str, float] | None = None

    @model_validator(mode="after")
    def validate_calibration(self):
        required = set(BAND_MAP[self.provider].values())
        if not required <= self.digital_numbers.keys():
            raise ValueError("Missing required raw bands")
        if any(not 0 <= value <= 65535 for value in self.digital_numbers.values()):
            raise ValueError("Digital numbers must be uint16")
        if self.provider == SatelliteProvider.sentinel_2:
            if self.sentinel_quantification is None or not isfinite(self.sentinel_quantification):
                raise ValueError("Sentinel quantification metadata required")
            if self.sentinel_offsets is None or not required <= self.sentinel_offsets.keys():
                raise ValueError("Sentinel per-band offsets required")
            if any(not isfinite(value) for value in self.sentinel_offsets.values()):
                raise ValueError("Sentinel offsets must be finite")
        return self

def calibrate_reflectance(sample: CalibrationInput) -> ReflectanceSample:
    mapping = BAND_MAP[sample.provider]
    values = {}
    for name, band in mapping.items():
        dn = sample.digital_numbers[band]
        if dn == 0:
            raise ValueError("No-data digital number cannot be calibrated")
        if sample.provider == SatelliteProvider.sentinel_2:
            value = (dn + sample.sentinel_offsets[band]) / sample.sentinel_quantification
        else:
            value = dn * 0.0000275 - 0.2
        values[name] = value
    return ReflectanceSample(**values)
