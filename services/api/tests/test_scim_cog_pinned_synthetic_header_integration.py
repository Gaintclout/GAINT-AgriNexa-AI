"""Offline synthetic GeoTIFF integration through the real pinned header reader.

These tests exercise the actual TIFF header parser and HTTP range validator,
not mocked metadata planning functions. No network traffic occurs.
"""

import io

import pytest

from app.scim_cog_header_probe import inspect_remote_tiff_header
from app.scim_cog_pinned_metadata_opener import PinnedMetadataOpener
from app.scim_cog_range_fetch import RangeFetchError


URL = "https://sentinel-cogs.s3.us-west-2.amazonaws.com/synthetic.tif"
ETAG = '"synthetic-scene-1"'

HEADER = (
    b"II"
    + (42).to_bytes(2, "little")
    + (16).to_bytes(4, "little")
    + bytes(8)
)

OBJECT = HEADER + bytes(48)


class SyntheticResponse:
    status = 206

    def __init__(self, request, *, etag=ETAG, content=OBJECT):
        self._url = request.full_url

        # FIX: Return only the requested 16-byte range.
        # The complete synthetic object remains 64 bytes.
        self._body = io.BytesIO(content[:16])

        self.headers = {
            "ETag": etag,
            "Content-Range": f"bytes 0-15/{len(content)}",
            "Content-Length": "16",
        }

    def geturl(self):
        return self._url

    def read(self, size=-1):
        return self._body.read(size)

    def close(self):
        self._body.close()

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()


class SyntheticOpener:
    def __init__(self, *, etag=ETAG):
        self.etag = etag
        self.requests = []

    def open(self, request, timeout=15):
        self.requests.append(request)

        assert request.get_header("Range") == "bytes=0-15"

        return SyntheticResponse(
            request,
            etag=self.etag,
        )


def test_real_header_reader_with_pinned_transport():
    underlying = SyntheticOpener()
    pinned = PinnedMetadataOpener(underlying, ETAG)

    result = inspect_remote_tiff_header(
        URL,
        approved=True,
        opener=pinned,
    )

    assert result["format"] == "TIFF"
    assert result["first_ifd_offset"] == 16
    assert result["object_bytes"] == len(OBJECT)
    assert result["source_checksum_verified"] is False

    assert pinned.requests == 1
    assert underlying.requests[0].get_header("If-match") == ETAG


def test_real_header_reader_rejects_changed_version():
    pinned = PinnedMetadataOpener(
        SyntheticOpener(etag='"other-scene"'),
        ETAG,
    )

    with pytest.raises(RangeFetchError):
        inspect_remote_tiff_header(
            URL,
            approved=True,
            opener=pinned,
        )

    assert pinned.requests == 0


def test_real_header_reader_requires_approval():
    underlying = SyntheticOpener()
    pinned = PinnedMetadataOpener(underlying, ETAG)

    with pytest.raises(RangeFetchError, match="approval"):
        inspect_remote_tiff_header(
            URL,
            approved=False,
            opener=pinned,
        )

    assert underlying.requests == []


def test_real_header_reader_rejects_bad_tiff_signature():
    class BadOpener(SyntheticOpener):
        def open(self, request, timeout=15):
            self.requests.append(request)

            return SyntheticResponse(
                request,
                content=b"XX" + OBJECT[2:],
            )

    pinned = PinnedMetadataOpener(
        BadOpener(),
        ETAG,
    )

    with pytest.raises(RangeFetchError, match="byte order"):
        inspect_remote_tiff_header(
            URL,
            approved=True,
            opener=pinned,
        )
