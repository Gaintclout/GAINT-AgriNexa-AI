"""Offline polygon-to-pixel mask regression tests."""
import pytest
from app.scim_parcel_polygon_mask import rasterize_parcel_mask
from app.scim_cog_range_fetch import RangeFetchError
from app.scim_parcel_masked_indices import analyze_masked_reflectance

SQUARE={"type":"Polygon","coordinates":[[
    [0,0],[2,0],[2,2],[0,2],[0,0]]]}
GRID={"width":3,"height":3,"transform":(1,0,0,0,-1,3),"crs":"EPSG:4326"}

def test_pixel_center_mask():
    result=rasterize_parcel_mask(SQUARE,**GRID)
    assert result["mask"]==[False,False,False,True,True,False,True,True,False]
    assert result["parcel_pixels"]==4

def test_mask_feeds_existing_vegetation_analysis():
    mask=rasterize_parcel_mask(SQUARE,**GRID)["mask"]
    result=analyze_masked_reflectance([0.2]*9,[0.6]*9,
        [0.4]*9,[0.3]*9,mask)
    assert result["parcel_pixels"]==4
    assert result["valid_pixels"]==4
    assert result["mean_indices"]["ndvi"]==0.5

def test_polygon_outside_grid():
    shifted={**GRID,"transform":(1,0,10,0,-1,13)}
    result=rasterize_parcel_mask(SQUARE,**shifted)
    assert result["parcel_pixels"]==0

@pytest.mark.parametrize("parcel",[
    {"type":"Point","coordinates":[0,0]},
    {"type":"Polygon","coordinates":[]},
    {"type":"Polygon","coordinates":[[[0,0],[2,2],[0,2],[2,0],[0,0]]]},
    {"type":"Polygon","coordinates":[[[0,0],[1,0],[1,1],[0,1]]]},
    {"type":"Polygon","coordinates":[[[0,0],[181,0],[1,1],[0,0]]]},
])
def test_invalid_parcels_rejected(parcel):
    with pytest.raises(RangeFetchError):
        rasterize_parcel_mask(parcel,**GRID)

def test_rejects_rotated_grid():
    with pytest.raises(RangeFetchError):
        rasterize_parcel_mask(SQUARE,width=3,height=3,
            transform=(1,0.1,0,0,-1,3),crs="EPSG:4326")

def test_rejects_oversized_grid():
    with pytest.raises(RangeFetchError,match="budget"):
        rasterize_parcel_mask(SQUARE,width=1001,height=1000,
            transform=GRID["transform"],crs=GRID["crs"])

def test_rejects_unsupported_crs():
    with pytest.raises(RangeFetchError,match="CRS"):
        rasterize_parcel_mask(SQUARE,width=3,height=3,
            transform=GRID["transform"],crs="EPSG:3857")
