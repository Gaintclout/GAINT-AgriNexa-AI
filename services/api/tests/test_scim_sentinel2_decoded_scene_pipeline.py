"""Synthetic five-band pinned decoder to parcel indices integration tests."""
from copy import deepcopy
import pytest
from app.scim_sentinel2_decoded_scene_pipeline import analyze_decoded_sentinel2_scene
from app.scim_cog_range_fetch import RangeFetchError

PARCEL={"type":"Polygon","coordinates":[[
    [0,0],[2,0],[2,2],[0,2],[0,0]]]}
SCENE={"id":"SYNTHETIC_S2","collection":"sentinel-2-l2a",
       "captured_at":"2026-01-01T10:00:00Z"}
CALIBRATION={"quantification":10000,
             "offsets":{k:0 for k in ("B04","B08","B03","B11")}}
def asset(band,value,coarse=False):
    n=1 if coarse else 2
    return {"scene_id":"SYNTHETIC_S2","band":band,
            "raster":{"width":n,"height":n,"tile_width":n,
                      "tile_height":n,"crs":"EPSG:4326",
                      "transform":(2,0,0,0,-2,2) if coarse else
                                  (1,0,0,0,-1,2)},
            "decoded":{"pixel_values_decoded":True,
                       "object_version_pinned":True,
                       "metadata_version_pinned":True,
                       "tiles":[{"index":0,"row":0,"column":0,
                                 "pixels":[value]*(n*n)}]}}
def assets():
    return {"B04":asset("B04",2000),"B08":asset("B08",6000),
            "B03":asset("B03",4000),"B11":asset("B11",3000,True),
            "SCL":asset("SCL",4)}
def analyze(data):
    return analyze_decoded_sentinel2_scene(PARCEL,SCENE,data,CALIBRATION)

def test_five_decoded_assets_to_parcel_indices():
    result=analyze(assets())
    assert result["decoded_tile_grids_assembled"]==5
    assert result["parcel_pixels"]==4
    assert result["clear_pixels"]==4
    assert result["valid_pixels"]==4
    assert result["mean_indices"]["ndvi"]==0.5
    assert result["mean_indices"]["ndmi"]==0.333333
    assert result["raster_georeferencing_authenticated"] is False

@pytest.mark.parametrize("mutation",[
    lambda a:a["B04"].update(scene_id="OTHER"),
    lambda a:a["B08"].update(band="B04"),
    lambda a:a["B11"]["decoded"].update(metadata_version_pinned=False),
    lambda a:a["B03"]["decoded"]["tiles"].clear(),
    lambda a:a["SCL"]["decoded"]["tiles"][0].update(pixels=[12]*4),
    lambda a:a["B04"]["raster"].update(transform=(1,0,1,0,-1,2)),
])
def test_rejects_invalid_or_inconsistent_assets(mutation):
    data=assets()
    mutation(data)
    with pytest.raises(RangeFetchError):
        analyze(data)

def test_rejects_missing_asset():
    data=assets()
    del data["SCL"]
    with pytest.raises(RangeFetchError):
        analyze(data)

def test_rejects_unpinned_object():
    data=assets()
    data["B04"]["decoded"]["object_version_pinned"]=False
    with pytest.raises(RangeFetchError):
        analyze(data)
