"""Read-only SCIM processing plan validation; no jobs are scheduled."""
from datetime import datetime, timezone
from math import isfinite
from pydantic import BaseModel, Field, model_validator
from .scim_contracts import SatelliteProvider
from .scim_asset_review import REQUIRED
from .scim_processing_stages import processing_stages

class PlanRequest(BaseModel):
    provider: SatelliteProvider
    parcel_id: str = Field(min_length=1, max_length=128)
    scene_id: str = Field(min_length=1, max_length=200)
    captured_at: datetime
    available_bands: list[str] = Field(min_length=1, max_length=32)
    cloud_cover_percent: float = Field(ge=0, le=100)
    max_cloud_percent: float = Field(default=30, ge=0, le=100)

    @model_validator(mode="after")
    def check_scene(self):
        if self.captured_at.tzinfo is None or self.captured_at.utcoffset() is None:
            raise ValueError("Scene timestamp requires timezone")
        if self.captured_at.astimezone(timezone.utc) > datetime.now(timezone.utc):
            raise ValueError('Future acquisition is not allowed')
        if not isfinite(self.cloud_cover_percent) or not isfinite(self.max_cloud_percent):
            raise ValueError('Cloud measurements must be finite')
        if self.cloud_cover_percent > self.max_cloud_percent:
            raise ValueError("Scene exceeds cloud cover threshold")
        missing = set(REQUIRED[self.provider]) - set(self.available_bands)
        if missing:
            raise ValueError("Missing required bands: " + ", ".join(sorted(missing)))
        return self

def preview_plan(request: PlanRequest) -> dict:
    return {"parcel_id": request.parcel_id, "scene_id": request.scene_id,
            "provider": request.provider, "stages": processing_stages(),
            "execution_enabled": False}
