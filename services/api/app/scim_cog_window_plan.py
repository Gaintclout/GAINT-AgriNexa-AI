"""Bounded parcel-window planning for local, approved COG/GeoTIFF assets.

This module is offline. Remote HTTP range fetching needs separate authorization,
byte-budget enforcement, and network hardening before it can be enabled.
"""
from pathlib import Path
from math import ceil, floor, isfinite
import rasterio
from rasterio.windows import Window, bounds as window_bounds
from rasterio.warp import transform_bounds
from shapely.geometry import shape
from .scim_rasterio_pipeline import _trusted_path, MAX_PIXELS

MAX_WINDOW_PIXELS = MAX_PIXELS
MAX_MARGIN_PIXELS = 2

def plan_parcel_window(root: Path, filename: str, parcel_geometry: dict,
                       *, margin_pixels: int = 1) -> dict:
    """Plan an exact bounded window without reading raster pixels."""
    if type(margin_pixels) is not int or not 0 <= margin_pixels <= MAX_MARGIN_PIXELS:
        raise ValueError("Invalid window margin")
    polygon = shape(parcel_geometry)
    if polygon.geom_type not in ("Polygon", "MultiPolygon") or polygon.is_empty or not polygon.is_valid:
        raise ValueError("Valid parcel polygon required")
    west, south, east, north = polygon.bounds
    if not all(isfinite(x) for x in (west, south, east, north)):
        raise ValueError("Nonfinite parcel coordinates")
    if not (-180 <= west < east <= 180 and -90 <= south < north <= 90):
        raise ValueError("Parcel must be WGS84")
    path = _trusted_path(root, filename)
    with rasterio.open(path, "r", sharing=False) as src:
        if src.driver != "GTiff" or src.count != 1 or src.crs is None or src.dtypes[0] != "uint16":
            raise ValueError("Single-band uint16 georeferenced GeoTIFF required")
        if not src.transform.is_rectilinear or src.transform.a <= 0 or src.transform.e >= 0:
            raise ValueError("Unsupported raster transform")
        projected = transform_bounds("EPSG:4326", src.crs, west, south, east, north, densify_pts=21)
        if not all(isfinite(x) for x in projected):
            raise ValueError("Invalid projected parcel bounds")
        left, bottom, right, top = projected
        inverse = ~src.transform
        col0 = max(0, floor((left - src.transform.c) / src.transform.a) - margin_pixels)
        col1 = min(src.width, ceil((right - src.transform.c) / src.transform.a) + margin_pixels)
        row0 = max(0, floor((src.transform.f - top) / abs(src.transform.e)) - margin_pixels)
        row1 = min(src.height, ceil((src.transform.f - bottom) / abs(src.transform.e)) + margin_pixels)
        width, height = col1 - col0, row1 - row0
        if width <= 0 or height <= 0:
            raise ValueError("Parcel does not intersect raster extent")
        if width * height > MAX_WINDOW_PIXELS:
            raise ValueError("Parcel window exceeds pixel budget")
        window = Window(col0, row0, width, height)
        return {"filename": filename, "col_off": col0, "row_off": row0,
                "width": width, "height": height, "pixels": width * height,
                "crs": str(src.crs), "bounds": list(window_bounds(window, src.transform)),
                "pixel_data_read": False, "network_access": False,
                "checksum_verified": False, "provenance_verified": False}
