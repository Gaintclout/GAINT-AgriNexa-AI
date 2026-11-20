"""GeoTIFF UTM GeoKey decoder for trusted bounded metadata tuples.

Use only with GeoKeyDirectoryTag entries already retrieved by the bounded
range probe. Metadata remains unauthenticated until independently verified.
"""
from .scim_cog_range_fetch import RangeFetchError

def decode_wgs84_geokeys(keys: tuple) -> str:
    if not isinstance(keys, (tuple, list)) or len(keys) < 4:
        raise RangeFetchError("Invalid GeoKey directory")
    if tuple(keys[:3]) != (1, 1, 0):
        raise RangeFetchError("Unsupported GeoKey directory version")
    n = keys[3]
    if type(n) is not int or not 2 <= n <= 64 or len(keys) != 4 + 4*n:
        raise RangeFetchError("Invalid GeoKey count")
    parsed = {}
    for i in range(n):
        key, location, count, value = keys[4+4*i:8+4*i]
        if key in parsed or location != 0 or count != 1:
            raise RangeFetchError("Unsupported GeoKey value")
        parsed[key] = value
    if parsed.get(1025) != 1:
        raise RangeFetchError("Only PixelIsArea supported")
    if parsed == {1024:2,1025:1,2048:4326}:
        return "EPSG:4326"
    epsg = parsed.get(3072)
    if (set(parsed) == {1024,1025,3072} and parsed[1024] == 1
            and type(epsg) is int and
            (32601 <= epsg <= 32660 or 32701 <= epsg <= 32760)):
        return f"EPSG:{epsg}"
    raise RangeFetchError("Unsupported projected GeoTIFF CRS")
