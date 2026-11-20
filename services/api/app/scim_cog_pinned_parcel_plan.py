"""Single ETag-pinned metadata planning session for remote parcel windows.

All existing metadata readers accept an opener; this wrapper supplies one
shared If-Match enforcing opener. Tile payload retrieval is a separate step.
"""
from urllib.request import build_opener
from .scim_discovery import NoRedirects
from .scim_cog_pinned_metadata_opener import PinnedMetadataOpener
from .scim_cog_remote_projected_parcel import plan_remote_projected_parcel
from .scim_cog_range_fetch import RangeFetchError

def plan_pinned_remote_parcel(url, parcel, *, expected_etag, approved=False,
                              margin_pixels=1, opener=None):
    if not approved:
        raise RangeFetchError("Explicit pinned parcel planning approval required")
    base=opener if opener is not None else build_opener(NoRedirects())
    pinned=PinnedMetadataOpener(base,expected_etag)
    plan=plan_remote_projected_parcel(
        url,parcel,approved=True,opener=pinned,margin_pixels=margin_pixels)
    if pinned.requests < 1:
        raise RangeFetchError("Pinned metadata inspection made no requests")
    return {**plan,"etag":expected_etag,"metadata_version_pinned":True,
            "metadata_range_requests":pinned.requests,
            "source_checksum_verified":False,"provenance_verified":False}
