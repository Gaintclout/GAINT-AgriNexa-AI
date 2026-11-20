"""Pinned parcel metadata integration checks without live HTTP."""
import pytest
from app import scim_cog_pinned_parcel_plan as module
from app.scim_cog_range_fetch import RangeFetchError

URL="https://sentinel-cogs.s3.us-west-2.amazonaws.com/sample.tif"
ETAG='"scene-v1"'
PARCEL={"type":"Polygon","coordinates":[[
    [78.8599,18.1199],[78.8601,18.1199],[78.8601,18.1201],
    [78.8599,18.1201],[78.8599,18.1199]]]}

class Response:
    def __init__(self,etag=ETAG):
        self.headers={"ETag":etag}
        self.closed=False
    def close(self):
        self.closed=True

class Opener:
    def __init__(self,etag=ETAG):
        self.etag=etag
        self.requests=[]
    def open(self,request,timeout=15):
        self.requests.append(request)
        return Response(self.etag)

def fake_plan(url,parcel,*,approved,opener,margin_pixels):
    from urllib.request import Request
    opener.open(Request(url,headers={"Range":"bytes=0-15"}))
    opener.open(Request(url,headers={"Range":"bytes=16-31"}))
    return {"crs":"EPSG:32644","pixel_window":{
        "col":1,"row":2,"width":3,"height":4},"tile_indices":[0]}

def test_metadata_plan_uses_one_etag(monkeypatch):
    monkeypatch.setattr(module,"plan_remote_projected_parcel",fake_plan)
    opener=Opener()
    result=module.plan_pinned_remote_parcel(
        URL,PARCEL,expected_etag=ETAG,approved=True,opener=opener)
    assert result["metadata_version_pinned"] is True
    assert result["metadata_range_requests"]==2
    assert all(r.get_header("If-match")==ETAG for r in opener.requests)
    assert result["source_checksum_verified"] is False

def test_requires_approval_before_transport(monkeypatch):
    monkeypatch.setattr(module,"plan_remote_projected_parcel",
                        lambda *a,**k:pytest.fail("unexpected metadata read"))
    with pytest.raises(RangeFetchError,match="approval"):
        module.plan_pinned_remote_parcel(URL,PARCEL,expected_etag=ETAG)

def test_changed_metadata_etag_fails(monkeypatch):
    monkeypatch.setattr(module,"plan_remote_projected_parcel",fake_plan)
    with pytest.raises(RangeFetchError,match="changed"):
        module.plan_pinned_remote_parcel(
            URL,PARCEL,expected_etag=ETAG,approved=True,
            opener=Opener('"scene-v2"'))

def test_no_metadata_requests_fails_closed(monkeypatch):
    monkeypatch.setattr(module,"plan_remote_projected_parcel",
                        lambda *a,**k:{"tile_indices":[0]})
    with pytest.raises(RangeFetchError,match="no requests"):
        module.plan_pinned_remote_parcel(
            URL,PARCEL,expected_etag=ETAG,approved=True,opener=Opener())
