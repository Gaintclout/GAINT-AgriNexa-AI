"""Mocked pinned COG HTTP transport tests; no network."""
import io
import pytest
from app.scim_cog_pinned_range_fetch import fetch_pinned_cog_range
from app.scim_cog_range_fetch import RangeFetchError

URL="https://sentinel-cogs.s3.us-west-2.amazonaws.com/example.tif"
ETAG='"immutable-v1"'

class Response:
    def __init__(self, *, status=206, etag=ETAG, body=b"abcd",
                 content_range="bytes 0-3/100", url=URL):
        self.status=status
        self.headers={"ETag":etag,"Content-Range":content_range,
                      "Content-Length":str(len(body))}
        self.body=io.BytesIO(body)
        self.url=url
    def geturl(self):
        return self.url
    def read(self,n=-1):
        return self.body.read(n)
    def __enter__(self):
        return self
    def __exit__(self,*args):
        self.body.close()

class Opener:
    def __init__(self,response):
        self.response=response
        self.requests=[]
    def open(self,request,timeout=None):
        self.requests.append(request)
        return self.response

def test_if_match_header_and_range():
    client=Opener(Response())
    result=fetch_pinned_cog_range(URL,0,4,expected_etag=ETAG,
                                  approved=True,opener=client)
    assert result["data"]==b"abcd"
    assert result["object_version_pinned"] is True
    assert result["source_checksum_verified"] is False
    assert client.requests[0].get_header("If-match")==ETAG
    assert client.requests[0].get_header("Range")=="bytes=0-3"

def test_approval_before_transport():
    client=Opener(Response())
    with pytest.raises(RangeFetchError,match="approval"):
        fetch_pinned_cog_range(URL,0,4,expected_etag=ETAG,opener=client)
    assert client.requests==[]

@pytest.mark.parametrize("response",[
    Response(status=200),Response(etag='"changed"'),
    Response(content_range="bytes 1-4/100"),
    Response(body=b"abc"),Response(url="https://example.org/redirect")])
def test_fail_closed_on_invalid_response(response):
    with pytest.raises(RangeFetchError):
        fetch_pinned_cog_range(URL,0,4,expected_etag=ETAG,
                               approved=True,opener=Opener(response))

@pytest.mark.parametrize("etag",["weak",'W/"weak"',''])
def test_invalid_expected_etag(etag):
    client=Opener(Response())
    with pytest.raises(RangeFetchError):
        fetch_pinned_cog_range(URL,0,4,expected_etag=etag,
                               approved=True,opener=client)
    assert client.requests==[]
