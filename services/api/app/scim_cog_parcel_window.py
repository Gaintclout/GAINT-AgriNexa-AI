"""Fail-closed parcel-to-pixel planning for independently verified EPSG:4326 grids.

The affine transform is caller-supplied trusted metadata, NOT extracted or
authenticated from the remote TIFF. No remote requests are made here.
"""
import math
from .scim_cog_range_fetch import RangeFetchError
from .scim_cog_window_tiles import select_window_tiles

MAX_PARCEL_VERTICES = 10000
MAX_WINDOW_PIXELS = 10000

def plan_parcel_pixel_window(table: dict, parcel: dict, *,
                             transform: tuple, crs: str,
                             margin_pixels: int = 1) -> dict:
    """Map a WGS84 Polygon onto an axis-aligned north-up WGS84 raster grid."""
    if crs != "EPSG:4326":
        raise RangeFetchError("Only independently verified EPSG:4326 is supported")
    if (not isinstance(transform, (tuple, list)) or len(transform) != 6
            or any(type(v) not in (float, int) or not math.isfinite(v) for v in transform)):
        raise RangeFetchError("Invalid affine transform")
    a, b, c, d, e, f = transform
    if a <= 0 or e >= 0 or b != 0 or d != 0:
        raise RangeFetchError("Only north-up nonrotated transforms are supported")
    if type(margin_pixels) is not int or not 0 <= margin_pixels <= 16:
        raise RangeFetchError("Invalid pixel margin")
    if not isinstance(parcel, dict) or parcel.get("type") != "Polygon":
        raise RangeFetchError("A WGS84 Polygon is required")
    rings = parcel.get("coordinates")
    if not isinstance(rings, list) or len(rings) != 1 or not isinstance(rings[0], list):
        raise RangeFetchError("Only a simple polygon without holes is supported")
    ring = rings[0]
    if not 4 <= len(ring) <= MAX_PARCEL_VERTICES or ring[0] != ring[-1]:
        raise RangeFetchError("Invalid or unclosed polygon")
    points = []
    for point in ring:
        if (not isinstance(point, (list, tuple)) or len(point) != 2 or
                any(type(v) not in (int, float) or not math.isfinite(v) for v in point)):
            raise RangeFetchError("Invalid parcel coordinate")
        lon, lat = point
        if not -180 <= lon <= 180 or not -90 <= lat <= 90:
            raise RangeFetchError("Parcel coordinate outside WGS84")
        points.append((lon, lat))
    area = sum(x1*y2 - x2*y1 for (x1,y1),(x2,y2) in zip(points, points[1:]))
    if abs(area) < 1e-12:
        raise RangeFetchError("Degenerate polygon")
    columns = [(lon - c) / a for lon, lat in points]
    rows = [(lat - f) / e for lon, lat in points]
    left = max(0, math.floor(min(columns)) - margin_pixels)
    top = max(0, math.floor(min(rows)) - margin_pixels)
    right = min(table["width"], math.ceil(max(columns)) + margin_pixels)
    bottom = min(table["height"], math.ceil(max(rows)) + margin_pixels)
    if right <= left or bottom <= top:
        raise RangeFetchError("Parcel does not overlap image")
    if (right - left) * (bottom - top) > MAX_WINDOW_PIXELS:
        raise RangeFetchError("Parcel window exceeds pixel budget")
    tiles = select_window_tiles(table, col=left, row=top,
                                width=right-left, height=bottom-top)
    return {"pixel_window": {"col": left, "row": top, "width": right-left,
                             "height": bottom-top},
            "tile_indices": [tile["index"] for tile in tiles],
            "georeferencing_source": "caller_supplied",
            "georeferencing_verified_from_tiff": False,
            "parcel_mask_applied": False, "source_checksum_verified": False,
            "provenance_verified": False}
