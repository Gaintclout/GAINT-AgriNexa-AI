"""Offline Sentinel-2 L2A calibration and parcel QA regression tests."""
import pytest
from app.scim_sentinel2_parcel_analysis import analyze_sentinel2_parcel
from app.scim_cog_range_fetch import RangeFetchError

PARCEL={"type":"Polygon","coordinates":[[
    [0,0],[2,0],[2,2],[0,2],[0,0]]]}
TRANSFORM=(1,0,0,0,-1,2)
OFFSETS={"B04":0,"B08":0,"B03":0,"B11":0}

def grid(values,*,coarse=False):
    return {"width":1 if coarse else 2,"height":1 if coarse else 2,
            "crs":"EPSG:4326",
            "transform":(2,0,0,0,-2,2) if coarse else TRANSFORM,
            "values":values}

def inputs():
    bands={"red":grid([2000]*4),"nir":grid([6000]*4),
           "green":grid([4000]*4),"swir1":grid([3000],coarse=True)}
    return bands,grid([4,8,5,6])

def test_calibration_cloud_mask_and_coarse_swir():
    bands,scl=inputs()
    result=analyze_sentinel2_parcel(PARCEL,bands,scl,
        quantification=10000,offsets=OFFSETS)
    assert result["parcel_pixels"]==4
    assert result["clear_pixels"]==3
    assert result["valid_pixels"]==3
    assert result["mean_indices"]=={
        "ndvi":0.5,"ndwi":-0.2,"ndmi":0.333333}
    assert result["resampled_bands"]==["swir1"]
    assert result["reflectance_calibrated"] is True
    assert result["calibration_metadata_verified"] is False

def test_all_cloudy_pixels_produce_null_indices():
    bands,scl=inputs()
    scl["values"]=[8]*4
    result=analyze_sentinel2_parcel(PARCEL,bands,scl,
        quantification=10000,offsets=OFFSETS)
    assert result["clear_pixels"]==0
    assert result["valid_pixels"]==0
    assert result["mean_indices"]["ndvi"] is None

def test_zero_dn_excluded_from_valid():
    bands,scl=inputs()
    bands["red"]["values"][0]=0
    result=analyze_sentinel2_parcel(PARCEL,bands,scl,
        quantification=10000,offsets=OFFSETS)
    assert result["clear_pixels"]==3
    assert result["valid_pixels"]==2

def test_coarse_scl_alignment():
    bands,_=inputs()
    result=analyze_sentinel2_parcel(PARCEL,bands,grid([4],coarse=True),
        quantification=10000,offsets=OFFSETS)
    assert result["clear_pixels"]==4
    assert result["scl_resampled"] is True

@pytest.mark.parametrize("quantification",[0,-1,float("nan")])
def test_rejects_invalid_quantification(quantification):
    bands,scl=inputs()
    with pytest.raises(RangeFetchError):
        analyze_sentinel2_parcel(PARCEL,bands,scl,
            quantification=quantification,offsets=OFFSETS)

def test_rejects_missing_offsets():
    bands,scl=inputs()
    with pytest.raises(RangeFetchError):
        analyze_sentinel2_parcel(PARCEL,bands,scl,
            quantification=10000,offsets={"B04":0})

def test_rejects_invalid_scl_classification():
    bands,scl=inputs()
    scl["values"][0]=12
    with pytest.raises(RangeFetchError):
        analyze_sentinel2_parcel(PARCEL,bands,scl,
            quantification=10000,offsets=OFFSETS)

def test_rejects_misaligned_scl():
    bands,scl=inputs()
    scl["transform"]=(1,0,1,0,-1,2)
    with pytest.raises(RangeFetchError):
        analyze_sentinel2_parcel(PARCEL,bands,scl,
            quantification=10000,offsets=OFFSETS)
