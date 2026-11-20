"""Bounded parcel pixel windows for WGS84 and Sentinel-2 WGS84 UTM grids.

Caller-supplied transform and CRS are NOT independently authenticated.
"""
import math
from .scim_cog_range_fetch import RangeFetchError
from .scim_cog_window_tiles import select_window_tiles
from .scim_cog_parcel_window import MAX_PARCEL_VERTICES, MAX_WINDOW_PIXELS

def plan_projected_parcel_window(table: dict, parcel: dict, *, transform,
                                 crs: str, margin_pixels: int = 1) -> dict:
    if crs == "EPSG:4326":
        from .scim_cog_parcel_window import plan_parcel_pixel_window
        return plan_parcel_pixel_window(table, parcel, transform=transform,
                                        crs=crs, margin_pixels=margin_pixels)
    try:
        epsg = int(crs.removeprefix("EPSG:")) if isinstance(crs, str) and crs.startswith("EPSG:") else -1
    except ValueError:
        epsg = -1
    if not (32601 <= epsg <= 32660 or 32701 <= epsg <= 32760):
        raise RangeFetchError("Only WGS84 UTM zones 1-60 are supported")
    if (not isinstance(transform, (tuple, list)) or len(transform) != 6 or
            any(type(v) not in (float, int) or not math.isfinite(v) for v in transform)):
        raise RangeFetchError("Invalid affine transform")
    a, b, c, d, e, f = transform
    if a <= 0 or e >= 0 or b != 0 or d != 0:
        raise RangeFetchError("Only north-up nonrotated grids are supported")
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
        if (not isinstance(point, (tuple, list)) or len(point) != 2 or
                any(type(v) not in (float, int) or not math.isfinite(v) for v in point)):
            raise RangeFetchError("Invalid WGS84 coordinates")
        lon, lat = point
        if not -180 <= lon <= 180 or not -90 <= lat <= 90:
            raise RangeFetchError("Coordinates outside WGS84")
        points.append((lon, lat))
    if abs(sum(x1*y2-x2*y1 for (x1,y1),(x2,y2) in zip(points,points[1:]))) < 1e-12:
        raise RangeFetchError("Degenerate parcel polygon")
    try:
        from pyproj import Transformer
        transformer = Transformer.from_crs("EPSG:4326", crs, always_xy=True)
        projected = [transformer.transform(lon, lat, errcheck=True) for lon,lat in points]
    except Exception as exc:
        raise RangeFetchError("WGS84 to UTM transformation failed") from exc
    if not all(math.isfinite(v) for pair in projected for v in pair):
        raise RangeFetchError("Nonfinite projected coordinates")
    cols = [(x-c)/a for x,y in projected]
    rows = [(y-f)/e for x,y in projected]
    left = max(0, math.floor(min(cols))-margin_pixels)
    top = max(0, math.floor(min(rows))-margin_pixels)
    right = min(table["width"], math.ceil(max(cols))+margin_pixels)
    bottom = min(table["height"], math.ceil(max(rows))+margin_pixels)
    if right <= left or bottom <= top:
        raise RangeFetchError("Parcel does not overlap image")
    width, height = right-left, bottom-top
    if width*height > MAX_WINDOW_PIXELS:
        raise RangeFetchError("Parcel window exceeds pixel budget")
    tiles = select_window_tiles(table, col=left, row=top, width=width, height=height)
    return {"pixel_window": {"col":left,"row":top,"width":width,"height":height},
            "tile_indices": [tile["index"] for tile in tiles],
            "georeferencing_source":"caller_supplied",
            "georeferencing_verified_from_tiff":False,
            "parcel_mask_applied":False,"source_checksum_verified":False,
            "provenance_verified":False}
