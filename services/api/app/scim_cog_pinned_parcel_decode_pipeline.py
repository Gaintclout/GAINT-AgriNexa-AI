"""One approved, ETag-pinned remote parcel retrieval and bounded decoding workflow.

All metadata inspections use the same caller-supplied strong ETag. The
retrieval pipeline rechecks the parcel plan. Decode metadata and tile table
are inspected again under the same ETag; object size and tile byte counts
are checked before decoding. No checksum, provenance, parcel mask, or
vegetation index is claimed.
"""
from urllib.request import build_opener
from .scim_discovery import NoRedirects
from .scim_cog_range_fetch import RangeFetchError
from .scim_cog_pinned_metadata_opener import PinnedMetadataOpener
from .scim_cog_pinned_parcel_pipeline import retrieve_pinned_parcel
from .scim_cog_tile_table import inspect_remote_tile_table
from .scim_cog_decode_tags_probe import inspect_remote_decode_tags
from .scim_cog_pinned_tile_decode import decode_pinned_parcel_tiles

def retrieve_and_decode_pinned_parcel(url,parcel,*,expected_etag,
                                      approved=False,margin_pixels=1,opener=None):
    if not approved:
        raise RangeFetchError("Explicit pinned parcel decoding approval required")
    base=opener if opener is not None else build_opener(NoRedirects())
    retrieved=retrieve_pinned_parcel(
        url,parcel,expected_etag=expected_etag,approved=True,
        margin_pixels=margin_pixels,opener=base)
    pinned=PinnedMetadataOpener(base,expected_etag)
    table=inspect_remote_tile_table(url,approved=True,opener=pinned)
    tags=inspect_remote_decode_tags(url,approved=True,opener=pinned)
    if table["object_bytes"]!=tags["object_bytes"]:
        raise RangeFetchError("Pinned TIFF metadata object size mismatch")
    result=decode_pinned_parcel_tiles(retrieved,table,tags)
    return {"crs":retrieved["crs"],"pixel_window":retrieved["pixel_window"],
            **result,"object_version_pinned":True,
            "metadata_version_pinned":True,
            "decode_tags_validated":True}
