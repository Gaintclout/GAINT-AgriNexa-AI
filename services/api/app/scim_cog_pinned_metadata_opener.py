"""Adapter for existing GeoTIFF parsers using a version-pinned opener.

The existing parsers call fetch_cog_range, which builds HTTP Range requests.
This adapter adds If-Match and validates response ETags before parser reads,
without changing global module state. It is intended only for parsers that
accept an opener argument. HTTP response validation remains in the original
range fetcher, and this adapter adds immutable-object checks.
"""
from urllib.request import Request
from .scim_cog_object_version import validate_object_version
from .scim_cog_range_fetch import RangeFetchError

class PinnedMetadataOpener:
    def __init__(self, opener, expected_etag):
        if opener is None:
            raise RangeFetchError("An explicit HTTP opener is required")
        validate_object_version({"ETag":expected_etag},expected_etag=expected_etag)
        self._opener=opener
        self.expected_etag=expected_etag
        self.object_bytes=None
        self.requests=0

    def open(self, request, timeout=15):
        if not isinstance(request,Request):
            raise RangeFetchError("Expected a validated range request")
        if request.get_header("Range") is None:
            raise RangeFetchError("Missing HTTP Range header")
        request.add_header("If-Match",self.expected_etag)
        response=self._opener.open(request,timeout=timeout)
        try:
            validate_object_version(response.headers,
                                    expected_etag=self.expected_etag)
            self.requests+=1
            return response
        except Exception:
            response.close()
            raise
