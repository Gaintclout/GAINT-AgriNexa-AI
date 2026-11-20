"""Strict GeoKey decoding for geographic WGS84 and projected UTM."""
import pytest
from app.scim_cog_utm_geokeys import decode_wgs84_geokeys
from app.scim_cog_range_fetch import RangeFetchError

def directory(*records):
    result = [1,1,0,len(records)]
    for record in records:
        result.extend(record)
    return tuple(result)

def test_geographic_wgs84():
    assert decode_wgs84_geokeys(directory((1024,0,1,2),(1025,0,1,1),(2048,0,1,4326))) == "EPSG:4326"

@pytest.mark.parametrize("epsg", [32601,32644,32660,32701,32744,32760])
def test_utm_zone(epsg):
    assert decode_wgs84_geokeys(directory((1024,0,1,1),(1025,0,1,1),(3072,0,1,epsg))) == f"EPSG:{epsg}"

@pytest.mark.parametrize("epsg", [32600,32661,32700,32761,3857])
def test_bad_utm_zone(epsg):
    with pytest.raises(RangeFetchError):
        decode_wgs84_geokeys(directory((1024,0,1,1),(1025,0,1,1),(3072,0,1,epsg)))

def test_duplicate_key_rejected():
    with pytest.raises(RangeFetchError):
        decode_wgs84_geokeys(directory((1024,0,1,1),(1025,0,1,1),(3072,0,1,32644),(3072,0,1,32644)))

def test_external_key_rejected():
    with pytest.raises(RangeFetchError):
        decode_wgs84_geokeys(directory((1024,0,1,1),(1025,0,1,1),(3072,34737,1,32644)))
