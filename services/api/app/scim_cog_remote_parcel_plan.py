"""Fail-closed remote GeoTIFF parcel tile planning.

Reads remote grid metadata and tile table; no tile payload is downloaded.
The TIFF metadata is not independently authenticated.
"""
from .scim_cog_geotiff_probe import inspect_remote_geotiff_grid
from .scim_cog_tile_table import inspect_remote_tile_table
from .scim_cog_parcel_window import plan_parcel_pixel_window
from .scim_cog_range_fetch import RangeFetchError

def plan_remote_parcel_tiles(url: str, parcel: dict, *, approved: bool = False,
                             opener=None, margin_pixels: int = 1) -> dict:
    """Plan tiles only when remote metadata and grid dimensions agree."""
    if not approved:
        raise RangeFetchError("Explicit remote metadata approval required")
    grid = inspect_remote_geotiff_grid(url, approved=approved, opener=opener)
    table = inspect_remote_tile_table(url, approved=approved, opener=opener)
    if grid["crs"] != "EPSG:4326":
        raise RangeFetchError("Unsupported remote CRS")
    planned = plan_parcel_pixel_window(
        table, parcel, transform=tuple(grid["transform"]),
        crs=grid["crs"], margin_pixels=margin_pixels)
    return {
        "pixel_window": planned["pixel_window"],
        "tile_indices": planned["tile_indices"],
        "tile_count": len(planned["tile_indices"]),
        "crs": grid["crs"], "transform": grid["transform"],
        "image_width": table["width"], "image_height": table["height"],
        "georeferencing_tags_parsed": True,
        "tile_ranges_verified": table["tile_ranges_verified"],
        "tile_payload_downloaded": False,
        "pixel_values_decoded": False,
        "parcel_mask_applied": False,
        "source_authenticated": False,
        "source_checksum_verified": False,
        "provenance_verified": False,
    }
