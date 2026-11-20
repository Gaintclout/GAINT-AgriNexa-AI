"""No-network tests for bounded remote parcel tile retrieval."""
import pytest
from app import scim_cog_remote_parcel_fetch as module
from app.scim_cog_range_fetch import RangeFetchError

URL = "https://sentinel-cogs.s3.us-west-2.amazonaws.com/synthetic.tif"
PARCEL = {"type":"Polygon","coordinates":[[
    [78.8599,18.1199],[78.8601,18.1199],[78.8601,18.1201],
    [78.8599,18.1201],[78.8599,18.1199]]]}
WINDOW = {"col":250,"row":250,"width":20,"height":20}
def plan(*args,**kwargs):
    return {"crs":"EPSG:32644","pixel_window":dict(WINDOW),
            "tile_indices":[0,1,2,3]}

def fetch(*args,**kwargs):
    return {"tiles":[{"index":i,"data":b"abc"} for i in range(4)],
            "tile_count":4,"tile_payload_bytes":12}

def test_retrieval_revalidates_plan(monkeypatch):
    calls=[]
    def checked_plan(*args,**kwargs):
        calls.append("plan")
        return plan()
    def checked_fetch(*args,**kwargs):
        calls.append("fetch")
        assert kwargs["col"]==250 and kwargs["height"]==20
        return fetch()
    monkeypatch.setattr(module,"plan_remote_projected_parcel",checked_plan)
    monkeypatch.setattr(module,"fetch_window_tile_bytes",checked_fetch)
    result=module.fetch_remote_parcel_tile_bytes(URL,PARCEL,approved=True)
    assert calls==["plan","fetch","plan"]
    assert result["tile_count"]==4
    assert result["source_checksum_verified"] is False
    assert result["remote_object_version_pinned"] is False

def test_approval_gate_before_network(monkeypatch):
    monkeypatch.setattr(module,"plan_remote_projected_parcel",
                        lambda *a,**k: pytest.fail("network metadata call"))
    with pytest.raises(RangeFetchError,match="approval"):
        module.fetch_remote_parcel_tile_bytes(URL,PARCEL)

def test_changed_tile_selection_rejected(monkeypatch):
    monkeypatch.setattr(module,"plan_remote_projected_parcel",plan)
    monkeypatch.setattr(module,"fetch_window_tile_bytes",
                        lambda *a,**k:{"tiles":[{"index":99,"data":b"x"}],
                                      "tile_count":1,"tile_payload_bytes":1})
    with pytest.raises(RangeFetchError,match="Tile selection"):
        module.fetch_remote_parcel_tile_bytes(URL,PARCEL,approved=True)

@pytest.mark.parametrize("change",["crs","window","indices"])
def test_changed_remote_metadata_rejected(monkeypatch,change):
    count=[0]
    def changing(*args,**kwargs):
        count[0]+=1
        result=plan()
        if count[0]==2:
            if change=="crs":
                result["crs"]="EPSG:32744"
            elif change=="window":
                result["pixel_window"]["col"]=251
            else:
                result["tile_indices"]=[0]
        return result
    monkeypatch.setattr(module,"plan_remote_projected_parcel",changing)
    monkeypatch.setattr(module,"fetch_window_tile_bytes",fetch)
    with pytest.raises(RangeFetchError,match="metadata changed"):
        module.fetch_remote_parcel_tile_bytes(URL,PARCEL,approved=True)
