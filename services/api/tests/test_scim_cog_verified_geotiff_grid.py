"""Offline GeoTIFF probe-to-decoded-grid consistency tests."""
import pytest
from app.scim_cog_verified_geotiff_grid import assemble_verified_geotiff_grid
from app.scim_cog_range_fetch import RangeFetchError

META={"width":2,"height":2,"tile_width":2,"tile_height":2,
      "crs":"EPSG:32644","transform":(10,0,500000,0,-10,2000000)}
TABLE={"width":2,"height":2,"tile_width":2,"tile_height":2,
       "object_bytes":4096}
GEOREF={"crs":"EPSG:32644","transform":(10,0,500000,0,-10,2000000),
        "object_bytes":4096}
DECODED={"pixel_values_decoded":True,"object_version_pinned":True,
         "metadata_version_pinned":True,
         "tiles":[{"index":0,"row":0,"column":0,"pixels":[1,2,3,4]}]}

def verify(decoded=None,table=None,georef=None,metadata=None):
    return assemble_verified_geotiff_grid(
        DECODED if decoded is None else decoded,
        TABLE if table is None else table,
        GEOREF if georef is None else georef,
        META if metadata is None else metadata)

def test_probe_checked_grid_assembly():
    result=verify()
    assert result["values"]==[1,2,3,4]
    assert result["georeferencing_source"]=="geotiff_probe"
    assert result["georeferencing_consistency_checked"] is True
    assert result["georeferencing_authenticated"] is False

@pytest.mark.parametrize("field,value",[
    ("width",3),("height",3),("tile_width",1),("tile_height",1)])
def test_rejects_tile_geometry_mismatch(field,value):
    with pytest.raises(RangeFetchError,match="geometry"):
        verify(table={**TABLE,field:value})

def test_rejects_crs_mismatch():
    with pytest.raises(RangeFetchError,match="CRS"):
        verify(georef={**GEOREF,"crs":"EPSG:32643"})

def test_rejects_affine_mismatch():
    with pytest.raises(RangeFetchError,match="affine"):
        verify(georef={**GEOREF,"transform":(10,0,500010,0,-10,2000000)})

def test_rejects_object_size_mismatch():
    with pytest.raises(RangeFetchError,match="size"):
        verify(georef={**GEOREF,"object_bytes":4097})

def test_rejects_unpinned_decoded_metadata():
    with pytest.raises(RangeFetchError,match="Pinned"):
        verify(decoded={**DECODED,"metadata_version_pinned":False})

def test_rejects_missing_metadata_field():
    data=dict(META)
    del data["crs"]
    with pytest.raises(RangeFetchError,match="Incomplete"):
        verify(metadata=data)

def test_rejects_invalid_tile_pixels():
    data={**DECODED,"tiles":[{"index":0,"row":0,"column":0,"pixels":[1]}]}
    with pytest.raises(RangeFetchError,match="pixel"):
        verify(decoded=data)
