"""Synthetic, offline UTM parcel-window regression tests."""
import pytest
from pyproj import Transformer
from app.scim_cog_utm_window import plan_projected_parcel_window
from app.scim_cog_range_fetch import RangeFetchError

P = {"type":"Polygon","coordinates":[[
    [78.8599,18.1199],[78.8601,18.1199],[78.8601,18.1201],
    [78.8599,18.1201],[78.8599,18.1199]]]}
T = Transformer.from_crs("EPSG:4326","EPSG:32644",always_xy=True)
X,Y = T.transform(78.86,18.12)
GRID = {"width":512,"height":512,"tile_width":256,"tile_height":256,
        "tile_columns":2,"tiles":[
            {"index":i,"row":i//2,"column":i%2,"byte_count":20}
            for i in range(4)]}
AFFINE = (10,0,X-2560,0,-10,Y+2560)

def plan(parcel=P, crs="EPSG:32644", transform=AFFINE, margin=0):
    return plan_projected_parcel_window(GRID,parcel,transform=transform,
                                        crs=crs,margin_pixels=margin)

def test_siddipet_utm44n_window():
    result = plan()
    assert result["pixel_window"]["width"] > 0
    assert result["pixel_window"]["height"] > 0
    assert result["tile_indices"] == [0,1,2,3]
    assert result["georeferencing_verified_from_tiff"] is False

@pytest.mark.parametrize("crs", ["EPSG:3857","EPSG:32600","EPSG:32761","bad"])
def test_unsupported_crs(crs):
    with pytest.raises(RangeFetchError,match="UTM"):
        plan(crs=crs)

def test_bad_polygon():
    with pytest.raises(RangeFetchError,match="Polygon"):
        plan(parcel={"type":"Point","coordinates":[78.86,18.12]})

def test_bad_transform():
    with pytest.raises(RangeFetchError,match="north-up"):
        plan(transform=(10,1,X,0,-10,Y))

def test_outside_raster():
    with pytest.raises(RangeFetchError,match="overlap"):
        plan(transform=(10,0,0,0,-10,0))

def test_margin_limit():
    with pytest.raises(RangeFetchError,match="margin"):
        plan(margin=17)
