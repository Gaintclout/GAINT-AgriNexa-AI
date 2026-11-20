"""One controlled ETag-pinned parcel planning and tile transfer operation.

Metadata and payload requests use the same caller-provided strong ETag.
The pinned plan is recomputed after transfer and compared before returning.
No checksum, provenance, or raster decoding is claimed.
"""
from .scim_cog_pinned_parcel_plan import plan_pinned_remote_parcel
from .scim_cog_pinned_parcel_tiles import fetch_pinned_parcel_tiles
from .scim_cog_tile_table import inspect_remote_tile_table
from .scim_cog_pinned_metadata_opener import PinnedMetadataOpener
from .scim_cog_range_fetch import RangeFetchError
from .scim_discovery import NoRedirects
from urllib.request import build_opener

def retrieve_pinned_parcel(url,parcel,*,expected_etag,approved=False,
                           margin_pixels=1,opener=None):
    if not approved:
        raise RangeFetchError("Explicit pinned parcel retrieval approval required")
    base=opener if opener is not None else build_opener(NoRedirects())
    before=plan_pinned_remote_parcel(
        url,parcel,expected_etag=expected_etag,approved=True,
        margin_pixels=margin_pixels,opener=base)
    metadata_opener=PinnedMetadataOpener(base,expected_etag)
    table=inspect_remote_tile_table(url,approved=True,opener=metadata_opener)
    selected=[]
    for index in before["tile_indices"]:
        if type(index) is not int or index < 0 or index >= len(table["tiles"]):
            raise RangeFetchError("Invalid pinned parcel tile index")
        selected.append(table["tiles"][index])
    payload=fetch_pinned_parcel_tiles(
        url,before,selected,expected_etag=expected_etag,
        expected_object_bytes=table["object_bytes"],approved=True,opener=base)
    after=plan_pinned_remote_parcel(
        url,parcel,expected_etag=expected_etag,approved=True,
        margin_pixels=margin_pixels,opener=base)
    if (before["crs"] != after["crs"] or
            before["pixel_window"] != after["pixel_window"] or
            before["tile_indices"] != after["tile_indices"]):
        raise RangeFetchError("Pinned parcel metadata changed during retrieval")
    return {"crs":before["crs"],"pixel_window":before["pixel_window"],
            "tiles":payload["tiles"],"tile_count":payload["tile_count"],
            "tile_payload_bytes":payload["tile_payload_bytes"],
            "object_version_pinned":True,"metadata_version_pinned":True,
            "source_checksum_verified":False,"provenance_verified":False,
            "pixel_values_decoded":False}
