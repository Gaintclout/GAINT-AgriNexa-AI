"""Synthetic offline Sentinel-2 scene bundle integration and rejection tests."""
from copy import deepcopy
import pytest
from app.scim_sentinel2_scene_bundle import analyze_sentinel2_scene_bundle
from app.scim_cog_range_fetch import RangeFetchError

PARCEL={"type":"Polygon","coordinates":[[
    [0,0],[2,0],[2,2],[0,2],[0,0]]]}
def grid(value,coarse=False):
    return {"width":1 if coarse else 2,"height":1 if coarse else 2,
            "crs":"EPSG:4326",
            "transform":(2,0,0,0,-2,2) if coarse else (1,0,0,0,-1,2),
            "values":[value]*(1 if coarse else 4)}
def bundle():
    values={"B04":grid(2000),"B08":grid(6000),
            "B03":grid(4000),"B11":grid(3000,True),
            "SCL":grid(4)}
    return {"scene":{"id":"SYNTHETIC_S2_SCENE","collection":"sentinel-2-l2a",
                     "captured_at":"2026-01-01T10:00:00Z"},
            "assets":{band:{"scene_id":"SYNTHETIC_S2_SCENE",
                             "band":band,"decoded":True,
                             "version_pinned":True,"grid":value}
                      for band,value in values.items()},
            "calibration":{"quantification":10000,
                           "offsets":{b:0 for b in ("B04","B08","B03","B11")}}}

def test_scene_bundle_to_parcel_indices():
    result=analyze_sentinel2_scene_bundle(PARCEL,bundle())
    assert result["scene_id"]=="SYNTHETIC_S2_SCENE"
    assert result["scene_assets_checked"]==5
    assert result["valid_pixels"]==4
    assert result["mean_indices"]["ndvi"]==0.5
    assert result["mean_indices"]["ndmi"]==0.333333
    assert result["scene_identity_authenticated"] is False
    assert result["provenance_verified"] is False

@pytest.mark.parametrize("change",[
    lambda b:b["scene"].update(collection="landsat-c2-l2"),
    lambda b:b["scene"].update(captured_at="2026-01-01T10:00:00"),
    lambda b:b["assets"]["B04"].update(scene_id="OTHER"),
    lambda b:b["assets"]["B08"].update(band="B04"),
    lambda b:b["assets"]["B11"].update(version_pinned=False),
    lambda b:b["assets"]["SCL"].update(decoded=False),
    lambda b:b["assets"].pop("SCL"),
    lambda b:b["calibration"].update(quantification=0),
    lambda b:b["calibration"]["offsets"].pop("B11"),
])
def test_rejects_inconsistent_scene_bundle(change):
    data=bundle()
    change(data)
    with pytest.raises(RangeFetchError):
        analyze_sentinel2_scene_bundle(PARCEL,data)

def test_rejects_misaligned_scene_band():
    data=bundle()
    data["assets"]["B08"]["grid"]["transform"]=(1,0,1,0,-1,2)
    with pytest.raises(RangeFetchError):
        analyze_sentinel2_scene_bundle(PARCEL,data)
