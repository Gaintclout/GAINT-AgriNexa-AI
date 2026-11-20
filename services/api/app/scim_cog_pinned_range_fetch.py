"""Version-aware HTTPS byte-range reads for SCIM COG assets.

Requires caller-supplied strong ETag; sends If-Match and verifies each response.
No redirects, decoding, file writes, or checksum/authenticity claims.
"""
from urllib.request import Request, build_opener
from urllib.error import HTTPError, URLError
from .scim_asset_url_policy import validate_asset_url
from .scim_discovery import NoRedirects
from .scim_cog_range_fetch import (
    RangeFetchError, MAX_RANGE_BYTES, MAX_OBJECT_BYTES, CONTENT_RANGE)
from .scim_cog_object_version import validate_object_version

def fetch_pinned_cog_range(url, start, length, *, expected_etag,
                           approved=False, opener=None):
    if not approved:
        raise RangeFetchError("Explicit pinned range approval required")
    validate_asset_url(url)
    if (type(start) is not int or type(length) is not int or start < 0 or
            not 1 <= length <= MAX_RANGE_BYTES or
            start + length > MAX_OBJECT_BYTES):
        raise RangeFetchError("Invalid or excessive byte range")
    validate_object_version({"ETag":expected_etag},expected_etag=expected_etag)
    end = start + length - 1
    request = Request(url,headers={
        "Range":f"bytes={start}-{end}",
        "If-Match":expected_etag,
        "Accept-Encoding":"identity",
        "User-Agent":"GAINT-AgriNexa-SCIM/0.1"})
    client = opener if opener is not None else build_opener(NoRedirects())
    try:
        with client.open(request,timeout=15) as response:
            if response.status != 206 or response.geturl() != url:
                raise RangeFetchError("Server did not honor pinned byte range")
            validate_object_version(response.headers,expected_etag=expected_etag)
            match = CONTENT_RANGE.fullmatch(response.headers.get("Content-Range",""))
            if match is None:
                raise RangeFetchError("Invalid Content-Range")
            actual_start,actual_end,total = map(int,match.groups())
            if (actual_start != start or actual_end != end or
                    total <= end or total > MAX_OBJECT_BYTES):
                raise RangeFetchError("Unexpected byte range or object size")
            declared = response.headers.get("Content-Length")
            if declared is not None:
                try:
                    declared_size = int(declared)
                except ValueError as exc:
                    raise RangeFetchError("Invalid Content-Length") from exc
                if declared_size != length:
                    raise RangeFetchError("Incorrect Content-Length")
            data = response.read(length+1)
            if len(data) != length or response.read(1):
                raise RangeFetchError("Truncated or oversized pinned range")
            return {"data":data,"start":start,"end":end,
                    "total_bytes":total,"etag":expected_etag,
                    "range_verified":True,"object_version_pinned":True,
                    "source_checksum_verified":False,"provenance_verified":False}
    except (HTTPError,URLError,TimeoutError,OSError) as exc:
        raise RangeFetchError("Pinned remote range request failed") from exc
