"""Explicitly authorized, byte-bounded HTTP range reads for trusted SCIM COG URLs.

This primitive does not parse GeoTIFFs, validate scene provenance or write files.
"""
import re
from urllib.request import Request, build_opener
from urllib.error import HTTPError, URLError
from .scim_asset_url_policy import validate_asset_url
from .scim_discovery import NoRedirects

MAX_RANGE_BYTES = 1024 * 1024
MAX_OBJECT_BYTES = 16 * 1024 * 1024 * 1024
CONTENT_RANGE = re.compile(r"^bytes ([0-9]+)-([0-9]+)/([0-9]+)$")

class RangeFetchError(ValueError):
    pass

def fetch_cog_range(url: str, start: int, length: int, *,
                    approved: bool = False, opener=None) -> dict:
    """Read at most 1 MiB with an exact 206 Content-Range response."""
    if not approved:
        raise RangeFetchError("Explicit remote range approval required")
    validate_asset_url(url)
    if (type(start) is not int or type(length) is not int or start < 0
            or not 1 <= length <= MAX_RANGE_BYTES or start + length > MAX_OBJECT_BYTES):
        raise RangeFetchError("Invalid or excessive byte range")
    end = start + length - 1
    request = Request(url, headers={
        "Range": f"bytes={start}-{end}",
        "Accept-Encoding": "identity",
        "User-Agent": "GAINT-AgriNexa-SCIM/0.1"})
    client = opener if opener is not None else build_opener(NoRedirects())
    try:
        with client.open(request, timeout=15) as response:
            if response.status != 206 or response.geturl() != url:
                raise RangeFetchError("Server did not honor exact range or redirected")
            if response.headers.get("Content-Encoding", "identity").lower() != "identity":
                raise RangeFetchError("Compressed range response rejected")
            match = CONTENT_RANGE.fullmatch(response.headers.get("Content-Range", ""))
            if match is None:
                raise RangeFetchError("Missing or invalid Content-Range")
            actual_start, actual_end, total = map(int, match.groups())
            if (actual_start != start or actual_end != end or total <= end
                    or total > MAX_OBJECT_BYTES):
                raise RangeFetchError("Unexpected range or object size")
            declared = response.headers.get("Content-Length")
            if declared is not None:
                try:
                    declared_size = int(declared)
                except ValueError as exc:
                    raise RangeFetchError("Invalid Content-Length") from exc
                if declared_size != length:
                    raise RangeFetchError("Incorrect Content-Length")
            data = response.read(length + 1)
            if len(data) != length or response.read(1):
                raise RangeFetchError("Truncated or oversized range response")
            return {"data": data, "start": start, "end": end, "total_bytes": total,
                    "range_verified": True, "source_checksum_verified": False,
                    "provenance_verified": False}
    except (HTTPError, URLError, TimeoutError, OSError) as exc:
        raise RangeFetchError("Remote range request failed") from exc
