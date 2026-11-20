"""Read restricted Classic GeoTIFF UTM georeferencing via bounded ranges."""
import math
import struct
from .scim_cog_header_probe import inspect_remote_tiff_header
from .scim_cog_range_fetch import fetch_cog_range, RangeFetchError
from .scim_cog_utm_geokeys import decode_wgs84_geokeys

def inspect_remote_projected_grid(url, *, approved=False, opener=None):
    if not approved:
        raise RangeFetchError("Explicit metadata access approval required")
    header = inspect_remote_tiff_header(url, approved=True, opener=opener)
    if header["format"] != "TIFF":
        raise RangeFetchError("Classic TIFF required")
    endian = "<" if header["byte_order"] == "little" else ">"
    total = header["object_bytes"]
    def read(offset, size):
        if offset < 0 or size < 1 or size > 4096 or offset + size > total:
            raise RangeFetchError("GeoTIFF metadata range outside object")
        result = fetch_cog_range(url, offset, size, approved=True, opener=opener)
        if result["total_bytes"] != total or len(result["data"]) != size:
            raise RangeFetchError("Remote object changed or truncated")
        return result["data"]
    ifd = header["first_ifd_offset"]
    n = struct.unpack(endian+"H", read(ifd,2))[0]
    if not 1 <= n <= 128:
        raise RangeFetchError("Invalid IFD size")
    entries = read(ifd+2, n*12+4)
    values = {}
    specs = {33550:(12,3),33922:(12,6),34735:(3,None)}
    for i in range(n):
        entry = entries[i*12:(i+1)*12]
        tag, typ, count, pointer = struct.unpack(endian+"HHII", entry)
        if tag not in specs:
            continue
        expected_type, expected_count = specs[tag]
        if tag in values or typ != expected_type or not count or (
            expected_count is not None and count != expected_count):
            raise RangeFetchError("Invalid georeferencing tag")
        size = count * (8 if typ == 12 else 2)
        if size > 4096:
            raise RangeFetchError("GeoTIFF tag too large")
        raw = entry[8:8+size] if size <= 4 else read(pointer,size)
        values[tag] = struct.unpack(endian+str(count)+("d" if typ==12 else "H"),raw)
    if set(values) != set(specs):
        raise RangeFetchError("Missing georeferencing tags")
    sx,sy,sz = values[33550]
    pi,pj,pk,x,y,z = values[33922]
    if (not all(math.isfinite(v) for v in (sx,sy,sz,pi,pj,pk,x,y,z))
            or sx <= 0 or sy <= 0 or sz != 0 or pk != 0 or z != 0):
        raise RangeFetchError("Unsupported georeferencing scale or tiepoint")
    crs = decode_wgs84_geokeys(values[34735])
    transform = (sx,0.0,x-pi*sx,0.0,-sy,y+pj*sy)
    if not all(math.isfinite(v) for v in transform):
        raise RangeFetchError("Invalid affine transform")
    return {"crs":crs,"transform":transform,"object_bytes":total,
            "source_authenticated":False,"source_checksum_verified":False,
            "provenance_verified":False}
