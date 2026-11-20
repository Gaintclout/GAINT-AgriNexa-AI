"""Parcel spectral summaries from pre-calibrated, quality-screened samples.

No imagery ingestion, geospatial clipping or persistence occurs here.
"""
from statistics import median
from pydantic import BaseModel, Field, model_validator
from .scim_indices import ReflectanceSample, SpectralIndices, calculate_indices

class ParcelSample(BaseModel):
    parcel_id: str = Field(min_length=1, max_length=128)
    scene_id: str = Field(min_length=1, max_length=200)
    reflectance: ReflectanceSample
    clear_pixel: bool

class ParcelSummaryRequest(BaseModel):
    parcel_id: str = Field(min_length=1, max_length=128)
    samples: list[ParcelSample] = Field(min_length=1, max_length=10000)

    @model_validator(mode="after")
    def matching_parcel(self):
        if any(sample.parcel_id != self.parcel_id for sample in self.samples):
            raise ValueError("All samples must belong to the requested parcel")
        return self

class ParcelSpectralSummary(BaseModel):
    parcel_id: str
    total_samples: int
    clear_samples: int
    valid_samples: int
    ndvi_median: float | None
    ndwi_median: float | None
    ndmi_median: float | None

def summarize_parcel(request: ParcelSummaryRequest) -> ParcelSpectralSummary:
    clear = [sample for sample in request.samples if sample.clear_pixel]
    indices = [calculate_indices(sample.reflectance) for sample in clear]
    valid = [item for item in indices if all(getattr(item, name) is not None for name in ("ndvi","ndwi","ndmi"))]
    def aggregate(name):
        values = [getattr(item, name) for item in valid]
        return round(median(values), 6) if values else None
    return ParcelSpectralSummary(
        parcel_id=request.parcel_id, total_samples=len(request.samples),
        clear_samples=len(clear), valid_samples=len(valid),
        ndvi_median=aggregate("ndvi"), ndwi_median=aggregate("ndwi"),
        ndmi_median=aggregate("ndmi"),
    )
