"""Offline co-registered parcel reflectance analysis tests."""
import pytest
from app.scim_parcel_registered_analysis import analyze_registered_parcel_bands
from app.scim_cog_range_fetch import RangeFetchError

PARCEL={"type":"Polygon","coordinates":[[
    [0,0],[2,0],[2,2],[0,2],[0,0]]]}
TRANSFORM=(1,0,0,0,-1,3)

def bands():
    return {name:{"width":3,"height":3,"crs":"EPSG:4326",
                  "transform":TRANSFORM,"values":[value]*9}
            for name,value in (("red",0.2),("nir",0.6),
                               ("green",0.4),("swir1",0.3))}

def test_registered_parcel_indices():
    result=analyze_registered_parcel_bands(PARCEL,bands())
    assert result["parcel_pixels"]==4
    assert result["valid_pixels"]==4
    assert result["mean_indices"]["ndvi"]==0.5
    assert result["mean_indices"]["ndwi"]==-0.2
    assert result["mean_indices"]["ndmi"]==0.333333
    assert result["band_coregistration_verified"] is True
    assert result["georeferencing_source"]=="caller_supplied"

@pytest.mark.parametrize("field,value",[
    ("width",4),("height",4),("crs","EPSG:32644"),
    ("transform",(1,0,1,0,-1,3))])
def test_rejects_misaligned_band(field,value):
    inputs=bands()
    inputs["nir"][field]=value
    with pytest.raises(RangeFetchError,match="co-registered"):
        analyze_registered_parcel_bands(PARCEL,inputs)

def test_rejects_missing_band():
    inputs=bands()
    del inputs["swir1"]
    with pytest.raises(RangeFetchError,match="Exactly"):
        analyze_registered_parcel_bands(PARCEL,inputs)

def test_rejects_extra_band():
    inputs=bands()
    inputs["blue"]=inputs["red"]
    with pytest.raises(RangeFetchError,match="Exactly"):
        analyze_registered_parcel_bands(PARCEL,inputs)

def test_rejects_pixel_length_mismatch():
    inputs=bands()
    inputs["red"]["values"]=[0.2]
    with pytest.raises(RangeFetchError,match="pixel count"):
        analyze_registered_parcel_bands(PARCEL,inputs)

def test_invalid_reflectance_excluded():
    inputs=bands()
    inputs["nir"]["values"][3]=float("nan")
    result=analyze_registered_parcel_bands(PARCEL,inputs)
    assert result["parcel_pixels"]==4
    assert result["valid_pixels"]==3
    assert result["invalid_pixels"]==1

def test_rejects_rotated_grid():
    inputs=bands()
    for grid in inputs.values():
        grid["transform"]=(1,0.1,0,0,-1,3)
    with pytest.raises(RangeFetchError,match="north-up"):
        analyze_registered_parcel_bands(PARCEL,inputs)
