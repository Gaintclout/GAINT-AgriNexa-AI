"""Fetch authoritative parcel geometry from PostGIS for SCIM clipping."""
import json
from sqlalchemy import select, func
from sqlalchemy.orm import Session
from .models import Parcel

def load_parcel_geometry(db: Session, parcel_id: str) -> dict:
    """Return a validated WGS84 GeoJSON MultiPolygon; never trust client masks."""
    geometry_json = db.scalar(
        select(func.ST_AsGeoJSON(Parcel.geom)).where(Parcel.id == parcel_id))
    if geometry_json is None:
        raise LookupError("Parcel not found or boundary not registered")
    geometry = json.loads(geometry_json)
    if geometry.get("type") not in ("Polygon", "MultiPolygon"):
        raise ValueError("Unsupported parcel geometry")
    return geometry
