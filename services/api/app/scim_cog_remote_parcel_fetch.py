"""Fail-closed remote parcel tile retrieval with independent plan revalidation.

Compressed tile bytes are untrusted and are never decoded by this module.
Revalidating metadata cannot prove immutable object identity; checksum and
provenance remain false, and production use requires version-pinned assets.
"""
from .scim_cog_remote_projected_parcel import plan_remote_projected_parcel
from .scim_cog_window_tiles import fetch_window_tile_bytes
from .scim_cog_range_fetch import RangeFetchError

def fetch_remote_parcel_tile_bytes(url, parcel, *, approved=False, opener=None,
                                   margin_pixels=1):
    if not approved:
        raise RangeFetchError("Explicit parcel tile retrieval approval required")
    before = plan_remote_projected_parcel(
        url, parcel, approved=True, opener=opener, margin_pixels=margin_pixels)
    window = before["pixel_window"]
    fetched = fetch_window_tile_bytes(
        url, col=window["col"], row=window["row"],
        width=window["width"], height=window["height"],
        approved=True, opener=opener)
    if [tile["index"] for tile in fetched["tiles"]] != before["tile_indices"]:
        raise RangeFetchError("Tile selection changed during retrieval")
    after = plan_remote_projected_parcel(
        url, parcel, approved=True, opener=opener, margin_pixels=margin_pixels)
    if (after["pixel_window"] != window or
            after["tile_indices"] != before["tile_indices"] or
            after["crs"] != before["crs"]):
        raise RangeFetchError("Remote parcel metadata changed during retrieval")
    return {
        "crs":before["crs"],"pixel_window":window,
        "tiles":fetched["tiles"],"tile_count":fetched["tile_count"],
        "tile_payload_bytes":fetched["tile_payload_bytes"],
        "pixel_values_decoded":False,"parcel_mask_applied":False,
        "remote_object_version_pinned":False,"source_authenticated":False,
        "source_checksum_verified":False,"provenance_verified":False}
