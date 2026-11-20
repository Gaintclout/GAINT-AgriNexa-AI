"""Version-pinned COG range session for metadata and tile inspection.

Use as a fetch_cog_range replacement in existing metadata parsers via a
module-level adapter. Every range in the session uses the same strong ETag.
"""
from .scim_cog_pinned_range_fetch import fetch_pinned_cog_range
from .scim_cog_object_version import validate_object_version
from .scim_cog_range_fetch import RangeFetchError

class PinnedRangeSession:
    def __init__(self, expected_etag, *, expected_object_bytes=None, opener=None):
        validate_object_version({"ETag":expected_etag},expected_etag=expected_etag)
        if expected_object_bytes is not None and (
                type(expected_object_bytes) is not int or expected_object_bytes < 1):
            raise RangeFetchError("Invalid expected object size")
        self.expected_etag=expected_etag
        self.expected_object_bytes=expected_object_bytes
        self.opener=opener
        self.requests=0

    def fetch(self,url,start,length,*,approved=False,opener=None):
        if not approved:
            raise RangeFetchError("Explicit pinned session approval required")
        if opener is not None and opener is not self.opener:
            raise RangeFetchError("Session opener override rejected")
        result=fetch_pinned_cog_range(
            url,start,length,expected_etag=self.expected_etag,
            approved=True,opener=self.opener)
        if self.expected_object_bytes is None:
            self.expected_object_bytes=result["total_bytes"]
        elif result["total_bytes"] != self.expected_object_bytes:
            raise RangeFetchError("Object size changed during pinned session")
        self.requests+=1
        return result
