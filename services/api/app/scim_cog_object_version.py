"""Strict immutable-object response validator for future COG range transport.

This is a validation primitive, not a claim that the existing range fetcher
enforces object pinning. Callers must pass headers from every HTTP 206 response.
"""
import re
from .scim_cog_range_fetch import RangeFetchError
_ETAG = re.compile(r'^"[\x21\x23-\x7e]{1,128}"$')
_SHA256 = re.compile(r"^[a-f0-9]{64}$")

def validate_object_version(headers, *, expected_etag=None, expected_sha256=None):
    """Require a strong, stable ETag and identity encoding on a range response."""
    etag = headers.get("ETag")
    if not isinstance(etag,str) or not _ETAG.fullmatch(etag) or etag.startswith('W/'):
        raise RangeFetchError("Missing or weak immutable-object ETag")
    if expected_etag is not None and etag != expected_etag:
        raise RangeFetchError("Remote object ETag changed")
    if headers.get("Content-Encoding","identity").lower() != "identity":
        raise RangeFetchError("Encoded object version response rejected")
    if expected_sha256 is not None and (
            not isinstance(expected_sha256,str) or
            not _SHA256.fullmatch(expected_sha256)):
        raise RangeFetchError("Invalid expected SHA256 digest")
    return {"etag":etag,"version_header_validated":True,
            "object_version_pinned":expected_etag is not None,
            "source_checksum_verified":False,"provenance_verified":False}
