"""Synthetic five-band GeoTIFF probe-consistent Sentinel-2 integration tests."""
import pytest
from app.scim_sentinel2_geotiff_checked_pipeline import (
    analyze_geotiff_checked_sentinel2_scene)
from app.scim_cog_range_fetch import RangeFetchError

PARCEL={"type":"Polygon","coordinates":[[
    [0,0],[2,0],[2,2],[0,0]]]}
SCENE={"id":"SYNTHETIC_S2","collection":"sentinel-2-l2a",
       "captured_at":"2026-01-01T10:00:00Z"}
CAL={"quantification":10000,"offsets":{
    "B04":0,"B08":0,"B03":0,"B11":0}}

def asset(band,value,coarse=False):
    n=1 if coarse else 2
    transform=(2,0,0,0,-2,2) if coarse else (1,0,0,0,-1,2)
    return {"scene_id":"SYNTHETIC_S2","band":band,
            "raster":{"width":n,"height":n,"tile_width":n,
                      "tile_height":n,"crs":"EPSG:4326",
                      "transform":transform},
            "tile_table":{"width":n,"height":n,"tile_width":n,
                          "tile_height":n,"object_bytes":4096},
            "georef":{"crs":"EPSG:4326","transform":transform,
                      "object_bytes":4096},
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
    return analyze_geotiff_checked_sentinel2_scene(PARCEL,SCENE,data,CAL)

def test_checked_geotiff_scene_to_indices():
    result=analyze(assets())
    assert result["geotiff_probe_checked_assets"]==5
    assert result["georeferencing_consistency_checked"] is True
    assert result["valid_pixels"]==3
    assert result["mean_indices"]["ndvi"]==0.5
    assert result["raster_georeferencing_authenticated"] is False

@pytest.mark.parametrize("mutation",[
    lambda a:a["B04"]["georef"].update(crs="EPSG:32644"),
    lambda a:a["B08"]["georef"].update(transform=(1,0,1,0,-1,2)),
    lambda a:a["B11"]["tile_table"].update(width=2),
    lambda a:a["B03"]["georef"].update(object_bytes=4097),
    lambda a:a["SCL"]["decoded"].update(metadata_version_pinned=False),
    lambda a:a["B04"].update(scene_id="OTHER"),
    lambda a:a["B08"].pop("georef"),
])
def test_rejects_mismatched_geotiff_probes(mutation):
    data=assets()
    mutation(data)
    with pytest.raises(RangeFetchError):
        analyze(data)
