"""Mocked network tests for fail-closed COG HTTP byte-range reads."""
from io import BytesIO
import pytest
from app.scim_cog_range_fetch import fetch_cog_range, RangeFetchError

URL = "https://sentinel-cogs.s3.us-west-2.amazonaws.com/test.tif"

class Response:
    def __init__(self, *, status=206, content_range="bytes 0-3/100",
                 data=b"abcd", url=URL, extra=None):
        self.status = status
        self.headers = {"Content-Range": content_range, "Content-Length": str(len(data))}
        if extra:
            self.headers.update(extra)
        self.url = url
        self.stream = BytesIO(data)
    def geturl(self):
        return self.url
    def read(self, count):
        return self.stream.read(count)
    def __enter__(self):
        return self
    def __exit__(self, *args):
        self.stream.close()

class Opener:
    def __init__(self, response):
        self.response = response
        self.calls = 0
    def open(self, request, timeout):
        self.calls += 1
        assert request.get_header("Range") == "bytes=0-3"
        return self.response

def test_exact_range_accepted():
    client = Opener(Response())
    result = fetch_cog_range(URL, 0, 4, approved=True, opener=client)
    assert result["data"] == b"abcd"
    assert result["range_verified"]
    assert not result["source_checksum_verified"]
    assert client.calls == 1

def test_approval_required_before_network():
    client = Opener(Response())
    with pytest.raises(RangeFetchError, match="approval"):
        fetch_cog_range(URL, 0, 4, opener=client)
    assert client.calls == 0

@pytest.mark.parametrize("response", [
    Response(status=200),
    Response(content_range="bytes 1-4/100"),
    Response(content_range="bytes 0-3/100", data=b"abc"),
    Response(extra={"Content-Encoding": "gzip"}),
    Response(url="https://example.com/redirect"),
    Response(content_range="bytes 0-3/999999999999"),
])
def test_invalid_range_responses_rejected(response):
    with pytest.raises(RangeFetchError):
        fetch_cog_range(URL, 0, 4, approved=True, opener=Opener(response))

def test_untrusted_host_rejected_without_network():
    client = Opener(Response())
    with pytest.raises(ValueError):
        fetch_cog_range("https://example.com/a.tif", 0, 4, approved=True, opener=client)
    assert client.calls == 0

@pytest.mark.parametrize("start,length", [(0, 0), (-1, 4), (0, 1048577), (True, 4)])
def test_invalid_byte_budget_rejected(start, length):
    with pytest.raises(RangeFetchError):
        fetch_cog_range(URL, start, length, approved=True, opener=Opener(Response()))
