"""SCIM scene intake contracts. No imagery is downloaded or persisted here."""
from datetime import datetime, timezone
from enum import Enum
from math import isfinite
from pydantic import BaseModel, Field, field_validator, model_validator

class SatelliteProvider(str, Enum):
    sentinel_2 = "sentinel-2"
    landsat_8 = "landsat-8"
    landsat_9 = "landsat-9"

class SceneCandidate(BaseModel):
    provider: SatelliteProvider
    scene_id: str = Field(min_length=1, max_length=200, pattern=r"^[A-Za-z0-9_.:-]+$")
    captured_at: datetime
    cloud_cover_percent: float = Field(ge=0, le=100)
    west: float = Field(ge=-180, le=180)
    south: float = Field(ge=-90, le=90)
    east: float = Field(ge=-180, le=180)
    north: float = Field(ge=-90, le=90)

    @field_validator("captured_at")
    @classmethod
    def require_aware_datetime(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("captured_at must include timezone")
        if value.astimezone(timezone.utc) > datetime.now(timezone.utc):
            raise ValueError("captured_at cannot be in the future")
        return value

    @field_validator("cloud_cover_percent", "west", "south", "east", "north")
    @classmethod
    def finite_number(cls, value: float) -> float:
        if not isfinite(value):
            raise ValueError("Coordinates and cloud cover must be finite")
        return value

    @model_validator(mode="after")
    def valid_bounds(self):
        if self.west >= self.east or self.south >= self.north:
            raise ValueError("Scene bounding box must have positive extent")
        return self

class SceneAssessment(BaseModel):
    scene_id: str
    provider: SatelliteProvider
    usable: bool
    reasons: list[str]
    cloud_cover_percent: float

def assess_scene(scene: SceneCandidate, maximum_cloud_percent: float) -> SceneAssessment:
    reasons = []
    if scene.cloud_cover_percent > maximum_cloud_percent:
        reasons.append("Cloud cover exceeds configured threshold")
    return SceneAssessment(scene_id=scene.scene_id, provider=scene.provider,
                           usable=not reasons, reasons=reasons,
                           cloud_cover_percent=scene.cloud_cover_percent)
