"""Build safe STAC 1.0 search requests for satellite catalog discovery.

This module prepares requests only; it does not call external catalogs.
"""
from datetime import datetime, timezone, timedelta
from math import isfinite
from pydantic import BaseModel, Field, field_validator, model_validator
from .scim_contracts import SatelliteProvider

COLLECTIONS = {
    SatelliteProvider.sentinel_2: "sentinel-2-l2a",
    SatelliteProvider.landsat_8: "landsat-c2-l2",
    SatelliteProvider.landsat_9: "landsat-c2-l2",
}

class CatalogSearch(BaseModel):
    provider: SatelliteProvider
    west: float = Field(ge=-180, le=180)
    south: float = Field(ge=-90, le=90)
    east: float = Field(ge=-180, le=180)
    north: float = Field(ge=-90, le=90)
    start: datetime
    end: datetime
    max_cloud_percent: float = Field(default=30, ge=0, le=100)
    limit: int = Field(default=20, ge=1, le=100)

    @field_validator("west", "south", "east", "north", "max_cloud_percent")
    @classmethod
    def finite(cls, value: float) -> float:
        if not isfinite(value):
            raise ValueError("Catalog coordinates and thresholds must be finite")
        return value

    @model_validator(mode="after")
    def valid_window(self):
        if self.west >= self.east or self.south >= self.north:
            raise ValueError("Invalid catalog search extent")
        if self.start.tzinfo is None or self.end.tzinfo is None:
            raise ValueError("Catalog timestamps require timezone")
        if self.start >= self.end:
            raise ValueError("Catalog start must precede end")
        if self.end.astimezone(timezone.utc) > datetime.now(timezone.utc):
            raise ValueError("Catalog search end cannot be in the future")
        if self.end - self.start > timedelta(days=366):
            raise ValueError("Catalog search period cannot exceed one year")
        return self

def build_stac_search(request: CatalogSearch) -> dict:
    return {
        "collections": [COLLECTIONS[request.provider]],
        "bbox": [request.west, request.south, request.east, request.north],
        "datetime": request.start.astimezone(timezone.utc).isoformat().replace("+00:00", "Z") + "/" + request.end.astimezone(timezone.utc).isoformat().replace("+00:00", "Z"),
        "limit": request.limit,
        "query": {"eo:cloud_cover": {"lte": request.max_cloud_percent}},
    }
