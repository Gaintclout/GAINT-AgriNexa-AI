"""Offline integration of real pinned TIFF tile-table and payload transfer.

Only geospatial parcel planning is stubbed; actual metadata HTTP range
validation and pinned tile transfer run against synthetic TIFF bytes.
"""
import io
import re
import struct
import pytest
from app import scim_cog_pinned_parcel_pipeline as pipeline
from app.scim_cog_range_fetch import RangeFetchError

URL="https://sentinel-cogs.s3.us-west-2.amazonaws.com/synthetic-parcel.tif"
ETAG='"synthetic-parcel-v1"'
PARCEL={"type":"Polygon","coordinates":[[
    [78.8599,18.1199],[78.8601,18.1199],[78.8601,18.1201],
    [78.8599,18.1201],[78.8599,18.1199]]]}
PLAN={"crs":"EPSG:32644","pixel_window":{
    "col":0,"row":0,"width":512,"height":256},"tile_indices":[0,1]}

def synthetic_tiff():
    data=bytearray(256)
    data[:8]=b"II"+struct.pack("<HI",42,16)
    tags=[(256,4,1,512),(257,4,1,256),(322,4,1,256),
          (323,4,1,256),(324,4,2,128),(325,4,2,136)]
    struct.pack_into("<H",data,16,len(tags))
    for i,tag in enumerate(tags):
        struct.pack_into("<HHII",data,18+i*12,*tag)
    struct.pack_into("<I",data,18+12*len(tags),0)
    struct.pack_into("<II",data,128,160,164)
    struct.pack_into("<II",data,136,4,4)
    data[160:168]=b"abcdefgh"
    return bytes(data)

class Response:
    status=206
    def __init__(self,url,data,start,end,etag):
        self._url=url
        self._body=io.BytesIO(data[start:end+1])
        self.headers={"ETag":etag,"Content-Range":f"bytes {start}-{end}/{len(data)}",
                      "Content-Length":str(end-start+1)}
    def geturl(self):
        return self._url
    def read(self,size=-1):
        return self._body.read(size)
    def close(self):
        self._body.close()
    def __enter__(self):
        return self
    def __exit__(self,*args):
        self.close()

class Opener:
    def __init__(self,data,*,change_at=None):
        self.data=data
        self.change_at=change_at
        self.calls=[]
    def open(self,request,timeout=15):
        self.calls.append(request)
        assert request.get_header("If-match")==ETAG
        match=re.fullmatch(r"bytes=(\d+)-(\d+)",request.get_header("Range",""))
        assert match is not None
        start,end=map(int,match.groups())
        assert 0<=start<=end<len(self.data)
        etag='"different-version"' if len(self.calls)==self.change_at else ETAG
        return Response(request.full_url,self.data,start,end,etag)

def stub_planning(monkeypatch):
    def plan(*args,**kwargs):
        assert kwargs["expected_etag"]==ETAG
        return {**PLAN,"pixel_window":dict(PLAN["pixel_window"]),
                "tile_indices":list(PLAN["tile_indices"])}
    monkeypatch.setattr(pipeline,"plan_pinned_remote_parcel",plan)

def test_real_pinned_tile_table_and_transfer(monkeypatch):
    stub_planning(monkeypatch)
    opener=Opener(synthetic_tiff())
    result=pipeline.retrieve_pinned_parcel(
        URL,PARCEL,expected_etag=ETAG,approved=True,opener=opener)
    assert result["tile_count"]==2
    assert result["tile_payload_bytes"]==8
    assert [tile["data"] for tile in result["tiles"]]==[b"abcd",b"efgh"]
    assert result["object_version_pinned"] is True
    assert result["metadata_version_pinned"] is True
    assert result["pixel_values_decoded"] is False
    assert result["source_checksum_verified"] is False
    assert len(opener.calls)>=7

def test_etag_drift_during_tile_download_fails_closed(monkeypatch):
    stub_planning(monkeypatch)
    opener=Opener(synthetic_tiff())
    # First five metadata reads: header, IFD count, IFD entries, two arrays.
    # The sixth range is the first tile payload.
    opener.change_at=6
    with pytest.raises(RangeFetchError):
        pipeline.retrieve_pinned_parcel(
            URL,PARCEL,expected_etag=ETAG,approved=True,opener=opener)
    assert len(opener.calls)==6

def test_unapproved_pipeline_does_not_fetch(monkeypatch):
    stub_planning(monkeypatch)
    opener=Opener(synthetic_tiff())
    with pytest.raises(RangeFetchError,match="approval"):
        pipeline.retrieve_pinned_parcel(
            URL,PARCEL,expected_etag=ETAG,opener=opener)
    assert opener.calls==[]
