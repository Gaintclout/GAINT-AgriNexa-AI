"""Offline pinned metadata opener tests."""
import io
import pytest
from urllib.request import Request
from app.scim_cog_pinned_metadata_opener import PinnedMetadataOpener
from app.scim_cog_range_fetch import RangeFetchError

ETAG='"scene-v1"'
URL="https://sentinel-cogs.s3.us-west-2.amazonaws.com/example.tif"

class Response:
    def __init__(self,etag=ETAG):
        self.headers={"ETag":etag}
        self.closed=False
    def close(self):
        self.closed=True

class Opener:
    def __init__(self,response):
        self.response=response
        self.calls=[]
    def open(self,request,timeout=15):
        self.calls.append(request)
        return self.response

def test_adds_if_match_to_range_request():
    underlying=Opener(Response())
    pinned=PinnedMetadataOpener(underlying,ETAG)
    req=Request(URL,headers={"Range":"bytes=0-15"})
    assert pinned.open(req) is underlying.response
    assert req.get_header("If-match")==ETAG
    assert pinned.requests==1

def test_rejects_changed_etag_and_closes_response():
    response=Response('"scene-v2"')
    pinned=PinnedMetadataOpener(Opener(response),ETAG)
    with pytest.raises(RangeFetchError,match="changed"):
        pinned.open(Request(URL,headers={"Range":"bytes=0-15"}))
    assert response.closed
    assert pinned.requests==0

def test_rejects_missing_range_before_transport():
    underlying=Opener(Response())
    pinned=PinnedMetadataOpener(underlying,ETAG)
    with pytest.raises(RangeFetchError,match="Range"):
        pinned.open(Request(URL))
    assert underlying.calls==[]

@pytest.mark.parametrize("etag",["weak",'W/"weak"',""])
def test_invalid_etag_rejected(etag):
    with pytest.raises(RangeFetchError):
        PinnedMetadataOpener(Opener(Response()),etag)
