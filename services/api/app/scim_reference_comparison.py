"""Independent-reference comparison gate for SCIM real satellite scenes.

Only compares supplied numerical results; it does not certify the source of
reference measurements. A successful comparison is not a production approval.
"""
from datetime import datetime, timezone
from math import isfinite
from pydantic import BaseModel, Field, model_validator

INDICES = ("ndvi_median", "ndwi_median", "ndmi_median")

class SceneReference(BaseModel):
    scene_id: str = Field(min_length=1, max_length=256)
    reference_source: str = Field(min_length=3, max_length=512)
    reference_method: str = Field(min_length=3, max_length=512)
    reference_timestamp: datetime
    parcel_pixels: int = Field(ge=1)
    clear_pixels: int = Field(ge=0)
    valid_pixels: int = Field(ge=1)
    ndvi_median: float
    ndwi_median: float
    ndmi_median: float

    @model_validator(mode="after")
    def validate_reference(self):
        if self.reference_timestamp.utcoffset() is None:
            raise ValueError("Reference timestamp must be timezone-aware")
        if not (self.valid_pixels <= self.clear_pixels <= self.parcel_pixels):
            raise ValueError("Reference pixel counts are inconsistent")
        if any(not isfinite(getattr(self, key)) or
               not -1 <= getattr(self, key) <= 1 for key in INDICES):
            raise ValueError("Reference indices must be finite within [-1, 1]")
        return self

class ComparisonTolerance(BaseModel):
    index_absolute: float = Field(default=0.03, ge=0, le=0.25)
    pixel_absolute: int = Field(default=0, ge=0, le=10000)

def compare_scene(actual: dict, reference: SceneReference,
                  tolerance: ComparisonTolerance | None = None) -> dict:
    tolerance = tolerance or ComparisonTolerance()
    checks = {}
    parcel = actual.get("parcel_pixels")
    clear = actual.get("clear_pixels")
    valid = actual.get("valid_pixels")
    checks["pixel_count_consistency"] = (all(type(n) is int for n in (parcel, clear, valid)) and
                                         0 < valid <= clear <= parcel)
    for key in ("parcel_pixels", "clear_pixels", "valid_pixels"):
        value = actual.get(key)
        checks[key] = (type(value) is int and value >= 0 and
                       abs(value - getattr(reference, key)) <= tolerance.pixel_absolute)
    for key in INDICES:
        value = actual.get(key)
        checks[key] = (isinstance(value, (float, int)) and
                       not isinstance(value, bool) and isfinite(value) and
                       -1 <= value <= 1 and
                       abs(value - getattr(reference, key)) <= tolerance.index_absolute)
    return {
        "scene_id": reference.scene_id,
        "reference_source": reference.reference_source,
        "reference_method": reference.reference_method,
        "checked_at": datetime.now(timezone.utc).isoformat(),
        "checks": checks,
        "passed": all(checks.values()),
        "status": "reference_comparison_only",
    }
