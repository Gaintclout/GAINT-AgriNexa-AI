"""Prepare safe read-only catalog searches from a WGS84 SCIM parcel polygon.

Only produces search parameters. It does not download imagery.
"""
from datetime import datetime, timezone
from math import isfinite
from .scim_catalog import CatalogSearch, build_stac_search

def parcel_bbox(geometry: dict) -> tuple[float, float, float, float]:
    if not isinstance(geometry, dict) or geometry.get("type") != "Polygon":
        raise ValueError("A WGS84 Polygon is required")
    rings = geometry.get("coordinates")
    if not isinstance(rings, list) or len(rings) != 1:
        raise ValueError("A single-ring test polygon is required")
    ring = rings[0]
    if not isinstance(ring, list) or not 4 <= len(ring) <= 1000:
        raise ValueError("Invalid polygon ring")
    points = []
    for point in ring:
        if (not isinstance(point, list) or len(point) != 2 or
                any(type(v) not in (int, float) or not isfinite(v) for v in point)):
            raise ValueError("Invalid WGS84 coordinate")
        lon, lat = point
        if not -180 <= lon <= 180 or not -90 <= lat <= 90:
            raise ValueError("WGS84 coordinate outside bounds")
        points.append((lon, lat))
    if points[0] != points[-1] or len(set(points[:-1])) < 3:
        raise ValueError("Polygon must be closed with three distinct vertices")
    west = min(p[0] for p in points)
    east = max(p[0] for p in points)
    south = min(p[1] for p in points)
    north = max(p[1] for p in points)
    if west >= east or south >= north:
        raise ValueError("Degenerate polygon bounds")
    return west, south, east, north

def parcel_catalog_searches(geometry: dict, start: datetime, end: datetime,
                            *, max_cloud_percent: float = 30, limit: int = 20) -> dict:
    bounds = parcel_bbox(geometry)
    return {provider: build_stac_search(CatalogSearch(
        provider=provider, west=bounds[0], south=bounds[1],
        east=bounds[2], north=bounds[3], start=start, end=end,
        max_cloud_percent=max_cloud_percent, limit=limit))
        for provider in ("sentinel-2", "landsat-8", "landsat-9")}
