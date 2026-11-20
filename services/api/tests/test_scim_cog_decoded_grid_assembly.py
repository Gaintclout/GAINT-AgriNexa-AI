"""Offline tests for decoded pinned TIFF tile-to-grid assembly."""
import pytest
from app.scim_cog_decoded_grid_assembly import assemble_decoded_tile_grid
from app.scim_cog_range_fetch import RangeFetchError

KW={"width":3,"height":2,"tile_width":2,"tile_height":2,
    "crs":"EPSG:4326","transform":(1,0,0,0,-1,2)}
def decoded():
    return {"pixel_values_decoded":True,"object_version_pinned":True,
            "metadata_version_pinned":True,
            "tiles":[{"index":0,"row":0,"column":0,"pixels":[1,2,3,4]},
                     {"index":1,"row":0,"column":1,"pixels":[5,99,6,99]}]}

def test_assembles_edge_tiles_without_padding():
    result=assemble_decoded_tile_grid(decoded(),**KW)
    assert result["values"]==[1,2,5,3,4,6]
    assert result["decoded"] is True
    assert result["version_pinned"] is True
    assert result["georeferencing_source"]=="caller_supplied"

def test_rejects_missing_tile():
    data=decoded()
    data["tiles"].pop()
    with pytest.raises(RangeFetchError,match="coverage"):
        assemble_decoded_tile_grid(data,**KW)

def test_rejects_duplicate_tile():
    data=decoded()
    data["tiles"][1]["index"]=0
    with pytest.raises(RangeFetchError):
        assemble_decoded_tile_grid(data,**KW)

def test_rejects_wrong_tile_position():
    data=decoded()
    data["tiles"][1]["column"]=0
    with pytest.raises(RangeFetchError):
        assemble_decoded_tile_grid(data,**KW)

def test_rejects_short_tile():
    data=decoded()
    data["tiles"][0]["pixels"]=[1]
    with pytest.raises(RangeFetchError,match="pixel count"):
        assemble_decoded_tile_grid(data,**KW)

def test_rejects_unpinned_tiles():
    data=decoded()
    data["metadata_version_pinned"]=False
    with pytest.raises(RangeFetchError,match="Pinned"):
        assemble_decoded_tile_grid(data,**KW)

def test_rejects_bad_pixel():
    data=decoded()
    data["tiles"][0]["pixels"][0]=-1
    with pytest.raises(RangeFetchError,match="pixel"):
        assemble_decoded_tile_grid(data,**KW)

def test_rejects_rotated_grid():
    with pytest.raises(RangeFetchError,match="north-up"):
        assemble_decoded_tile_grid(decoded(),**{**KW,"transform":(1,0.1,0,0,-1,2)})

def test_rejects_oversized_grid():
    with pytest.raises(RangeFetchError,match="budget"):
        assemble_decoded_tile_grid(decoded(),**{**KW,"width":1001,"height":1000})

def test_rejects_unexpected_extra_tile():
    data=decoded()
    data["tiles"].append(dict(data["tiles"][0]))
    with pytest.raises(RangeFetchError,match="coverage"):
        assemble_decoded_tile_grid(data,**KW)
