"""Input validation for WGS84 parcel polygons.

Topology validity is checked separately by PostGIS before storage.
"""
from math import isfinite
from fastapi import HTTPException

def normalize_boundary(value: dict) -> dict:
    if not isinstance(value, dict) or value.get("type") not in ("Polygon", "MultiPolygon"):
        raise HTTPException(422, "Expected GeoJSON Polygon or MultiPolygon")
    kind = value["type"]
    coordinates = value.get("coordinates")
    polygons = [coordinates] if kind == "Polygon" else coordinates
    if not isinstance(polygons, list) or not 1 <= len(polygons) <= 100:
        raise HTTPException(422, "Invalid polygon count")
    count = 0
    for polygon in polygons:
        if not isinstance(polygon, list) or not polygon:
            raise HTTPException(422, "Polygon requires at least one ring")
        for ring in polygon:
            if not isinstance(ring, list) or len(ring) < 4 or ring[0] != ring[-1]:
                raise HTTPException(422, "Each ring must contain four or more closed positions")
            count += len(ring)
            if count > 10000:
                raise HTTPException(422, "Boundary exceeds vertex limit")
            for point in ring:
                if not isinstance(point, list) or len(point) != 2:
                    raise HTTPException(422, "Coordinates must be longitude-latitude pairs")
                x, y = point
                if any(isinstance(v, bool) or not isinstance(v, (int, float)) or not isfinite(v) for v in point):
                    raise HTTPException(422, "Coordinates must be finite numbers")
                if not (-180 <= x <= 180 and -90 <= y <= 90):
                    raise HTTPException(422, "Coordinates outside WGS84 bounds")
    return {"type": "MultiPolygon", "coordinates": polygons}
