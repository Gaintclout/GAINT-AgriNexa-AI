"""Offline orchestration tests for pinned remote parcel decoding."""
import pytest
from app import scim_cog_pinned_parcel_decode_pipeline as pipeline
from app.scim_cog_range_fetch import RangeFetchError

URL="https://sentinel-cogs.s3.us-west-2.amazonaws.com/synthetic.tif"
ETAG='"synthetic-v1"'
PARCEL={"type":"Polygon","coordinates":[[[0,0],[1,0],[1,1],[0,1],[0,0]]]}

class FakeTransport:
    def __init__(self):
        self.calls=0
    def open(self,*args,**kwargs):
        self.calls+=1
        raise AssertionError("No real network calls expected")

def install(monkeypatch,*,size=256):
    calls=[]
    def retrieval(*args,**kwargs):
        calls.append(("retrieve",kwargs))
        return {"crs":"EPSG:32644","pixel_window":{"col":0,"row":0,"width":2,"height":2},
                "tiles":[{"index":0,"data":b"\x01\x02\x03\x04"}],
                "object_version_pinned":True,"metadata_version_pinned":True}
    def table(*args,**kwargs):
        calls.append(("table",kwargs))
        return {"object_bytes":256,"tile_width":2,"tile_height":2,
                "tiles":[{"index":0,"row":0,"column":0,"byte_count":4}]}
    def tags(*args,**kwargs):
        calls.append(("tags",kwargs))
        return {"object_bytes":size,"decode_tags_validated":True,
                "bits_per_sample":8,"compression":1,"byte_order":"little",
                "samples_per_pixel":1,"sample_format":1,"predictor":1}
    monkeypatch.setattr(pipeline,"retrieve_pinned_parcel",retrieval)
    monkeypatch.setattr(pipeline,"inspect_remote_tile_table",table)
    monkeypatch.setattr(pipeline,"inspect_remote_decode_tags",tags)
    return calls

def test_pinned_retrieval_metadata_and_decode(monkeypatch):
    calls=install(monkeypatch)
    transport=FakeTransport()
    result=pipeline.retrieve_and_decode_pinned_parcel(
        URL,PARCEL,expected_etag=ETAG,approved=True,opener=transport)
    assert result["tiles"][0]["pixels"]==[1,2,3,4]
    assert result["pixel_values_decoded"] is True
    assert result["decode_tags_validated"] is True
    assert result["parcel_mask_applied"] is False
    assert [name for name,_ in calls]==["retrieve","table","tags"]
    assert all(kwargs["approved"] is True for _,kwargs in calls)
    assert transport.calls==0

def test_rejects_mismatched_object_size(monkeypatch):
    install(monkeypatch,size=257)
    with pytest.raises(RangeFetchError,match="size"):
        pipeline.retrieve_and_decode_pinned_parcel(
            URL,PARCEL,expected_etag=ETAG,approved=True,opener=FakeTransport())

def test_unapproved_rejected_before_network(monkeypatch):
    calls=install(monkeypatch)
    transport=FakeTransport()
    with pytest.raises(RangeFetchError,match="approval"):
        pipeline.retrieve_and_decode_pinned_parcel(
            URL,PARCEL,expected_etag=ETAG,opener=transport)
    assert not calls
    assert transport.calls==0

def test_corrupt_tile_rejected(monkeypatch):
    install(monkeypatch)
    def bad(*args,**kwargs):
        return {"crs":"EPSG:32644","pixel_window":{},
                "tiles":[{"index":0,"data":b"x"}],
                "object_version_pinned":True,"metadata_version_pinned":True}
    monkeypatch.setattr(pipeline,"retrieve_pinned_parcel",bad)
    with pytest.raises(RangeFetchError,match="byte count"):
        pipeline.retrieve_and_decode_pinned_parcel(
            URL,PARCEL,expected_etag=ETAG,approved=True,opener=FakeTransport())
