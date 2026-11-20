"""Offline parcel vegetation index calculation regression tests."""
import pytest
from app.scim_parcel_masked_indices import analyze_masked_reflectance
from app.scim_cog_range_fetch import RangeFetchError

def test_masked_vegetation_means():
    result=analyze_masked_reflectance(
        [0.2,0.8,0.1],[0.6,0.2,0.5],[0.4,0.1,0.3],
        [0.3,0.2,0.25],[True,False,True])
    assert result["parcel_pixels"]==2
    assert result["valid_pixels"]==2
    assert result["mean_indices"]["ndvi"]==0.583333
    assert result["mean_indices"]["ndwi"]==-0.225
    assert result["mean_indices"]["ndmi"]==0.333333

def test_zero_denominators_are_null():
    result=analyze_masked_reflectance([0],[0],[0],[0],[True])
    assert result["mean_indices"]=={"ndvi":None,"ndwi":None,"ndmi":None}

def test_invalid_and_nodata_pixels_excluded():
    result=analyze_masked_reflectance(
        [0.2,-1,0.1],[0.6,0.2,0.5],[0.4,0.2,0.3],
        [0.3,0.2,0.25],[True,True,False],nodata=-1)
    assert result["valid_pixels"]==1
    assert result["invalid_pixels"]==1

def test_empty_parcel_coverage():
    result=analyze_masked_reflectance([0.2],[0.6],[0.4],[0.3],[False])
    assert result["parcel_pixels"]==0
    assert result["mean_indices"]["ndvi"] is None

@pytest.mark.parametrize("bands,mask",[
    (([0.2],[0.6],[0.4],[0.3]),[]),
    (([0.2],[0.6,0.7],[0.4],[0.3]),[True]),
    (([0.2],[0.6],[0.4],[0.3]),[1]),
    (([float("nan")],[0.6],[0.4],[0.3]),[True,False]),
])
def test_invalid_grids_rejected(bands,mask):
    with pytest.raises(RangeFetchError):
        analyze_masked_reflectance(*bands,mask)

def test_nonfinite_pixel_skipped():
    result=analyze_masked_reflectance(
        [float("nan")],[0.6],[0.4],[0.3],[True])
    assert result["invalid_pixels"]==1
    assert result["mean_indices"]["ndvi"] is None

def test_oversized_grid_rejected():
    with pytest.raises(RangeFetchError,match="aligned"):
        analyze_masked_reflectance([0]*1000001,[0]*1000001,
            [0]*1000001,[0]*1000001,[True]*1000001)
