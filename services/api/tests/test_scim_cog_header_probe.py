"""Offline mocked tests for bounded remote TIFF header inspection."""
from io import BytesIO
import pytest
from app.scim_cog_header_probe import inspect_remote_tiff_header
from app.scim_cog_range_fetch import RangeFetchError

URL = "https://sentinel-cogs.s3.us-west-2.amazonaws.com/sample.tif"

class Response:
    status = 206
    def __init__(self, payload, total=100):
        self.payload = BytesIO(payload)
        self.headers = {"Content-Range": f"bytes 0-15/{total}",
                        "Content-Length": "16"}
    def geturl(self):
        return URL
    def read(self, count):
        return self.payload.read(count)
    def __enter__(self):
        return self
    def __exit__(self, *args):
        self.payload.close()

class Opener:
    def __init__(self, payload, total=100):
        self.payload, self.total = payload, total
        self.calls = 0
    def open(self, request, timeout):
        self.calls += 1
        assert request.get_header("Range") == "bytes=0-15"
        return Response(self.payload, self.total)

def test_classic_little_endian_header():
    opener = Opener(b"II" + (42).to_bytes(2, "little") + (16).to_bytes(4, "little") + bytes(8))
    result = inspect_remote_tiff_header(URL, approved=True, opener=opener)
    assert result["format"] == "TIFF"
    assert result["first_ifd_offset"] == 16
    assert result["pixel_data_read"] is False
    assert result["cog_layout_verified"] is False

def test_big_endian_bigtiff_header():
    payload = b"MM" + (43).to_bytes(2, "big") + (8).to_bytes(2, "big") + bytes(2) + (32).to_bytes(8, "big")
    result = inspect_remote_tiff_header(URL, approved=True, opener=Opener(payload))
    assert result["format"] == "BigTIFF"
    assert result["first_ifd_offset"] == 32

def test_requires_approval_before_network():
    opener = Opener(bytes(16))
    with pytest.raises(RangeFetchError, match="approval"):
        inspect_remote_tiff_header(URL, opener=opener)
    assert opener.calls == 0

@pytest.mark.parametrize("payload,total", [
    (bytes(16), 100),
    (b"II" + (99).to_bytes(2, "little") + bytes(12), 100),
    (b"II" + (42).to_bytes(2, "little") + (200).to_bytes(4, "little") + bytes(8), 100),
    (b"II" + (43).to_bytes(2, "little") + (4).to_bytes(2, "little") + bytes(10), 100),
])
def test_invalid_headers_rejected(payload, total):
    with pytest.raises(RangeFetchError):
        inspect_remote_tiff_header(URL, approved=True, opener=Opener(payload, total))
