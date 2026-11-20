"""Bounding-box search and map GeoJSON for authorized GIS users."""
import json
from math import isfinite
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import text
from sqlalchemy.orm import Session
from .authorization import require_active_roles
from .database import get_db
from .security import Principal, Role
from .spatial_filters import normalize_filter

router = APIRouter(prefix="/api/v1/gis", tags=["gis"])
readers = (Role.admin, Role.gis_operator, Role.officer, Role.field_verifier, Role.ml_team)

def check_bbox(west: float, south: float, east: float, north: float) -> None:
    values = (west, south, east, north)
    if not all(isfinite(value) for value in values):
        raise HTTPException(422, "Bounding box must contain finite coordinates")
    if not (-180 <= west < east <= 180 and -90 <= south < north <= 90):
        raise HTTPException(422, "Invalid WGS84 bounding box")

@router.get("/parcels/geojson")
def parcel_features(
    west: float, south: float, east: float, north: float,
    limit: int = Query(default=100, ge=1, le=500),
    village_code: str | None = Query(default=None, max_length=100),
    external_id: str | None = Query(default=None, max_length=100),
    principal: Principal = Depends(require_active_roles(*readers, Role.farmer)),
    db: Session = Depends(get_db),
):
    check_bbox(west, south, east, north)
    village_code = normalize_filter(village_code, 'village_code')
    external_id = normalize_filter(external_id, 'external_id')
    query = text("""
        SELECT id, external_id, village_code, ST_AsGeoJSON(geom) AS geometry
        FROM parcels
        WHERE geom IS NOT NULL
          AND geom && ST_MakeEnvelope(:west, :south, :east, :north, 4326)
          AND ST_Intersects(geom, ST_MakeEnvelope(:west, :south, :east, :north, 4326))
          AND (CAST(:village_code AS varchar) IS NULL OR village_code = CAST(:village_code AS varchar))
          AND (CAST(:external_id AS varchar) IS NULL OR external_id = CAST(:external_id AS varchar))
          AND (CAST(:farmer_id AS varchar) IS NULL OR farmer_id = CAST(:farmer_id AS varchar))
        ORDER BY id
        LIMIT :limit
    """)
    farmer_id = principal.subject if principal.role == Role.farmer else None
    rows = db.execute(query, {"west": west, "south": south, "east": east, "north": north, "limit": limit, "village_code": village_code, "external_id": external_id, "farmer_id": farmer_id}).mappings()
    return {"type": "FeatureCollection", "features": [
        {"type": "Feature", "id": row["id"], "geometry": json.loads(row["geometry"]),
         "properties": {"external_id": row["external_id"], "village_code": row["village_code"]}}
        for row in rows
    ]}
