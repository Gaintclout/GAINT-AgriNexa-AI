"""Satellite-specific band mapping for calibrated reflectance samples."""
from pydantic import BaseModel, Field, model_validator
from .scim_contracts import SatelliteProvider
from .scim_indices import ReflectanceSample, SpectralIndices, calculate_indices

BAND_MAP = {
    SatelliteProvider.sentinel_2: {"red": "B04", "nir": "B08", "green": "B03", "swir1": "B11"},
    SatelliteProvider.landsat_8: {"red": "SR_B4", "nir": "SR_B5", "green": "SR_B3", "swir1": "SR_B6"},
    SatelliteProvider.landsat_9: {"red": "SR_B4", "nir": "SR_B5", "green": "SR_B3", "swir1": "SR_B6"},
}

class SensorBandSample(BaseModel):
    provider: SatelliteProvider
    bands: dict[str, float] = Field(min_length=4, max_length=20)

    @model_validator(mode="after")
    def validate_bands(self):
        missing = set(BAND_MAP[self.provider].values()) - set(self.bands)
        if missing:
            raise ValueError("Missing required sensor bands: " + ", ".join(sorted(missing)))
        return self

def calculate_sensor_indices(sample: SensorBandSample) -> SpectralIndices:
    mapping = BAND_MAP[sample.provider]
    reflectance = ReflectanceSample(**{name: sample.bands[band] for name, band in mapping.items()})
    return calculate_indices(reflectance)
