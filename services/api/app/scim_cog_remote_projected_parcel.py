"""Metadata-only remote parcel tile plan for WGS84 and UTM GeoTIFFs."""
from .scim_cog_projected_grid_probe import inspect_remote_projected_grid
from .scim_cog_tile_table import inspect_remote_tile_table
from .scim_cog_projected_plan import plan_projected_grid
from .scim_cog_range_fetch import RangeFetchError

def plan_remote_projected_parcel(url, parcel, *, approved=False, opener=None,
                                 margin_pixels=1):
    if not approved:
        raise RangeFetchError("Explicit remote metadata approval required")
    grid = inspect_remote_projected_grid(url, approved=True, opener=opener)
    table = inspect_remote_tile_table(url, approved=True, opener=opener)
    if grid["object_bytes"] != table["object_bytes"]:
        raise RangeFetchError("Remote TIFF object size mismatch")
    planned = plan_projected_grid(table, parcel, grid, margin_pixels=margin_pixels)
    return {"crs":grid["crs"],"pixel_window":planned["pixel_window"],
            "tile_indices":planned["tile_indices"],
            "tile_count":len(planned["tile_indices"]),
            "georeferencing_tags_parsed":True,
            "tile_payload_downloaded":False,
            "parcel_mask_applied":False,"source_authenticated":False,
            "source_checksum_verified":False,"provenance_verified":False}
