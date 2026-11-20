"""Mocked remote UTM parcel integration; no live imagery downloads."""
import pytest
from pyproj import Transformer
from app import scim_cog_remote_projected_parcel as module
from app.scim_cog_range_fetch import RangeFetchError

URL = "https://sentinel-cogs.s3.us-west-2.amazonaws.com/sample.tif"
PARCEL = {"type":"Polygon","coordinates":[[
    [78.8599,18.1199],[78.8601,18.1199],[78.8601,18.1201],
    [78.8599,18.1201],[78.8599,18.1199]]]}
X,Y = Transformer.from_crs("EPSG:4326","EPSG:32644",always_xy=True).transform(78.86,18.12)

def setup(monkeypatch, *, total=1000):
    calls=[]
    def grid(*args,**kwargs):
        calls.append("grid")
        return {"crs":"EPSG:32644","transform":(10,0,X-2560,0,-10,Y+2560),"object_bytes":1000}
    def table(*args,**kwargs):
        calls.append("table")
        return {"width":512,"height":512,"tile_width":256,"tile_height":256,
                "tile_columns":2,"object_bytes":total,
                "tiles":[{"index":i,"row":i//2,"column":i%2,"byte_count":20} for i in range(4)]}
    monkeypatch.setattr(module,"inspect_remote_projected_grid",grid)
    monkeypatch.setattr(module,"inspect_remote_tile_table",table)
    return calls

def test_siddipet_utm_parcel_plan(monkeypatch):
    calls=setup(monkeypatch)
    result=module.plan_remote_projected_parcel(URL,PARCEL,approved=True,margin_pixels=0)
    assert result["crs"]=="EPSG:32644"
    assert result["tile_indices"]==[0,1,2,3]
    assert result["tile_payload_downloaded"] is False
    assert calls==["grid","table"]

def test_approval_before_network(monkeypatch):
    calls=setup(monkeypatch)
    with pytest.raises(RangeFetchError,match="approval"):
        module.plan_remote_projected_parcel(URL,PARCEL)
    assert calls==[]

def test_remote_object_mismatch_rejected(monkeypatch):
    setup(monkeypatch,total=999)
    with pytest.raises(RangeFetchError,match="mismatch"):
        module.plan_remote_projected_parcel(URL,PARCEL,approved=True)
