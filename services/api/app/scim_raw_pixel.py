"""SCIM raw-pixel evaluation: QA mask -> calibration -> spectral indices.

Pure function only. It does not ingest imagery, align rasters or clip parcels.
"""
from pydantic import BaseModel, Field, model_validator
from .scim_calibration import CalibrationInput, calibrate_reflectance
from .scim_cloud_mask import PixelQuality, QualitySensor, is_clear_pixel
from .scim_contracts import SatelliteProvider
from .scim_indices import SpectralIndices, calculate_indices

class RawPixelInput(BaseModel):
    provider: SatelliteProvider
    qa_value: int = Field(ge=0, le=65535)
    calibration: CalibrationInput

    @model_validator(mode="after")
    def matching_provider(self):
        if self.provider != self.calibration.provider:
            raise ValueError("QA and calibration sensor must match")
        return self

class RawPixelResult(BaseModel):
    clear_pixel: bool
    indices: SpectralIndices | None

def evaluate_raw_pixel(sample: RawPixelInput) -> RawPixelResult:
    clear = is_clear_pixel(PixelQuality(
        sensor=QualitySensor(sample.provider.value), qa_value=sample.qa_value))
    if not clear:
        return RawPixelResult(clear_pixel=False, indices=None)
    calibrated = calibrate_reflectance(sample.calibration)
    return RawPixelResult(clear_pixel=True, indices=calculate_indices(calibrated))
