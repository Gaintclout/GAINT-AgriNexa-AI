"""Pinned metadata pipeline using a scoped replacement of range readers.

This implementation avoids global monkeypatching: a temporary module-level
override is unsafe under concurrent requests. Instead, the transport is
injected via an opener that validates each response ETag through a wrapper.
The existing range reader cannot send If-Match, so this adapter deliberately
fails closed until the parser accepts an explicit range-fetch callback.
"""
from .scim_cog_pinned_session import PinnedRangeSession
from .scim_cog_range_fetch import RangeFetchError

def require_pinned_metadata_pipeline(*, expected_etag, expected_object_bytes=None):
    """Construct the validated session; never silently use unpinned readers."""
    session=PinnedRangeSession(expected_etag,
                              expected_object_bytes=expected_object_bytes)
    return {"session":session,
            "metadata_pipeline_connected":False,
            "fail_closed":True,
            "reason":"Metadata parsers require injected pinned range transport"}
