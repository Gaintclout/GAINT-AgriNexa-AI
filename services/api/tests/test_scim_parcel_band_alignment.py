"""Offline exact 2x alignment and parcel analysis regression tests."""
import pytest
from app.scim_parcel_band_alignment import (
    align_reflectance_bands,analyze_aligned_parcel_bands)
from app.scim_cog_range_fetch import RangeFetchError

PARCEL={"type":"Polygon","coordinates":[[
    [0,0],[2,0],[2,2],[0,2],[0,0]]]}
def inputs():
    fine={"width":2,"height":2,"crs":"EPSG:4326",
          "transform":(1,0,0,0,-1,2),"values":[0.2]*4}
    coarse={"width":1,"height":1,"crs":"EPSG:4326",
            "transform":(2,0,0,0,-2,2),"values":[0.3]}
    return {"red":dict(fine),"nir":{**fine,"values":[0.6]*4},
            "green":{**fine,"values":[0.4]*4},"swir1":coarse}

def test_nearest_neighbor_2x_alignment():
    result=align_reflectance_bands(inputs())
    assert result["resampled_bands"]==["swir1"]
    assert result["bands"]["swir1"]["values"]==[0.3]*4
    assert result["bands"]["swir1"]["transform"]==(1,0,0,0,-1,2)

def test_aligned_parcel_indices():
    result=analyze_aligned_parcel_bands(PARCEL,inputs())
    assert result["parcel_pixels"]==4
    assert result["valid_pixels"]==4
    assert result["mean_indices"]["ndvi"]==0.5
    assert result["mean_indices"]["ndmi"]==0.333333
    assert result["resampled_bands"]==["swir1"]

def test_all_fine_bands_no_resampling():
    bands=inputs()
    bands["swir1"]={**bands["red"],"values":[0.3]*4}
    result=align_reflectance_bands(bands)
    assert result["resampled_bands"]==[]

@pytest.mark.parametrize("field,value",[
    ("crs","EPSG:32644"),
    ("transform",(2,0,1,0,-2,2)),
    ("transform",(2,0,0,0,-2,3)),
    ("transform",(2,0,0,0,-1,2)),
    ("width",2),
    ("height",2)])
def test_rejects_misaligned_coarse_band(field,value):
    bands=inputs()
    bands["swir1"][field]=value
    with pytest.raises(RangeFetchError):
        align_reflectance_bands(bands)

def test_rejects_missing_band():
    bands=inputs()
    del bands["green"]
    with pytest.raises(RangeFetchError):
        align_reflectance_bands(bands)

def test_rejects_rotated_target():
    bands=inputs()
    bands["red"]["transform"]=(1,0.1,0,0,-1,2)
    with pytest.raises(RangeFetchError):
        align_reflectance_bands(bands)

def test_rejects_invalid_pixel_count():
    bands=inputs()
    bands["swir1"]["values"]=[]
    with pytest.raises(RangeFetchError):
        align_reflectance_bands(bands)
