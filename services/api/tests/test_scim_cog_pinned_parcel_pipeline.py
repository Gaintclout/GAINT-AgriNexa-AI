"""Mocked end-to-end pinned parcel workflow tests; no external requests."""
import pytest
from app import scim_cog_pinned_parcel_pipeline as module
from app.scim_cog_range_fetch import RangeFetchError

URL="https://sentinel-cogs.s3.us-west-2.amazonaws.com/synthetic.tif"
ETAG='"scene-v1"'
PARCEL={"type":"Polygon","coordinates":[[
    [78.8599,18.1199],[78.8601,18.1199],[78.8601,18.1201],
    [78.8599,18.1201],[78.8599,18.1199]]]}
PLAN={"crs":"EPSG:32644","pixel_window":{
    "col":250,"row":250,"width":20,"height":20},"tile_indices":[0,1]}

def setup(monkeypatch,*,changed=False):
    calls=[]
    def plan(*args,**kwargs):
        calls.append("plan")
        assert kwargs["expected_etag"]==ETAG
        result={"crs":PLAN["crs"],"pixel_window":dict(PLAN["pixel_window"]),
                "tile_indices":list(PLAN["tile_indices"])}
        if changed and calls.count("plan")==2:
            result["pixel_window"]["col"]=251
        return result
    def table(*args,**kwargs):
        calls.append("table")
        return {"object_bytes":1000,"tiles":[
            {"index":0,"offset":100,"byte_count":2},
            {"index":1,"offset":200,"byte_count":3}]}
    def transfer(*args,**kwargs):
        calls.append("transfer")
        assert kwargs["expected_etag"]==ETAG
        assert kwargs["expected_object_bytes"]==1000
        return {"tiles":[{"index":0,"data":b"ab"},
                         {"index":1,"data":b"xyz"}],
                "tile_count":2,"tile_payload_bytes":5}
    monkeypatch.setattr(module,"plan_pinned_remote_parcel",plan)
    monkeypatch.setattr(module,"inspect_remote_tile_table",table)
    monkeypatch.setattr(module,"fetch_pinned_parcel_tiles",transfer)
    return calls

def test_full_pinned_workflow(monkeypatch):
    calls=setup(monkeypatch)
    result=module.retrieve_pinned_parcel(
        URL,PARCEL,expected_etag=ETAG,approved=True,opener=object())
    assert calls==["plan","table","transfer","plan"]
    assert result["metadata_version_pinned"] is True
    assert result["object_version_pinned"] is True
    assert result["source_checksum_verified"] is False

def test_requires_approval_before_network(monkeypatch):
    calls=setup(monkeypatch)
    with pytest.raises(RangeFetchError,match="approval"):
        module.retrieve_pinned_parcel(URL,PARCEL,expected_etag=ETAG,opener=object())
    assert calls==[]

def test_metadata_drift_rejected(monkeypatch):
    setup(monkeypatch,changed=True)
    with pytest.raises(RangeFetchError,match="changed"):
        module.retrieve_pinned_parcel(
            URL,PARCEL,expected_etag=ETAG,approved=True,opener=object())

def test_invalid_tile_index_rejected(monkeypatch):
    calls=setup(monkeypatch)
    monkeypatch.setattr(module,"plan_pinned_remote_parcel",
                        lambda *a,**k:{**PLAN,"tile_indices":[9]})
    with pytest.raises(RangeFetchError,match="tile index"):
        module.retrieve_pinned_parcel(
            URL,PARCEL,expected_etag=ETAG,approved=True,opener=object())
    assert "transfer" not in calls
