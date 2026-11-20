"""Bounded Classic GeoTIFF georeferencing tag probe (EPSG:4326 only).

Rejects unknown GeoKeys, rotations, multiple tiepoints and unsupported layouts.
Network metadata is untrusted; this does not authenticate the source or parcel.
"""
import math
import struct
from .scim_cog_header_probe import inspect_remote_tiff_header
from .scim_cog_range_fetch import fetch_cog_range, RangeFetchError

MAX_ENTRIES = 128
MAX_TAG_BYTES = 4096
TAGS = {33550: (12, 3), 33922: (12, 6), 34735: (3, None)}

def inspect_remote_geotiff_grid(url: str, *, approved: bool = False, opener=None) -> dict:
    if not approved:
        raise RangeFetchError("Explicit remote metadata approval required")
    header = inspect_remote_tiff_header(url, approved=approved, opener=opener)
    if header["format"] != "TIFF":
        raise RangeFetchError("Only Classic GeoTIFF is supported")
    order = "<" if header["byte_order"] == "little" else ">"
    total, ifd = header["object_bytes"], header["first_ifd_offset"]
    def read(start, length):
        if start < 0 or length < 1 or length > MAX_TAG_BYTES or start + length > total:
            raise RangeFetchError("GeoTIFF metadata outside bounded object")
        result = fetch_cog_range(url, start, length, approved=approved, opener=opener)
        if result["total_bytes"] != total:
            raise RangeFetchError("Remote object size changed")
        return result["data"]
    count = struct.unpack(order + "H", read(ifd, 2))[0]
    if not 1 <= count <= MAX_ENTRIES:
        raise RangeFetchError("Invalid GeoTIFF IFD entry count")
    entries = read(ifd + 2, count * 12 + 4)
    values = {}
    for index in range(count):
        entry = entries[index * 12:(index + 1) * 12]
        tag, typ, n = struct.unpack(order + "HHI", entry[:8])
        if tag not in TAGS:
            continue
        if tag in values:
            raise RangeFetchError("Duplicate GeoTIFF georeferencing tag")
        required_type, required_count = TAGS[tag]
        if typ != required_type or n == 0 or (required_count is not None and n != required_count):
            raise RangeFetchError("Unsupported GeoTIFF georeferencing tag")
        length = n * (8 if typ == 12 else 2)
        if length > MAX_TAG_BYTES:
            raise RangeFetchError("Oversized GeoTIFF tag")
        if length <= 4:
            raw = entry[8:8 + length]
        else:
            pointer = struct.unpack(order + "I", entry[8:12])[0]
            raw = read(pointer, length)
        fmt = "d" if typ == 12 else "H"
        values[tag] = struct.unpack(order + str(n) + fmt, raw)
    if set(values) != set(TAGS):
        raise RangeFetchError("Missing GeoTIFF georeferencing tags")
    scale, tie, keys = values[33550], values[33922], values[34735]
    if not all(math.isfinite(v) for v in (*scale, *tie)):
        raise RangeFetchError("Nonfinite GeoTIFF georeferencing")
    sx, sy, sz = scale
    if sx <= 0 or sy <= 0 or sz != 0:
        raise RangeFetchError("Unsupported GeoTIFF pixel scale")
    pixel_i, pixel_j, pixel_k, lon, lat, elevation = tie
    if pixel_k != 0 or elevation != 0:
        raise RangeFetchError("Unsupported 3D GeoTIFF tiepoint")
    if len(keys) < 4 or keys[0] != 1 or keys[1] != 1 or keys[2] != 0:
        raise RangeFetchError("Unsupported GeoKey directory")
    number = keys[3]
    if number < 2 or len(keys) != 4 + number * 4:
        raise RangeFetchError("Invalid GeoKey directory length")
    geokeys = {}
    for i in range(number):
        key, location, count, value = keys[4 + i * 4:8 + i * 4]
        if key in geokeys or location != 0 or count != 1:
            raise RangeFetchError("Unsupported GeoKey reference")
        geokeys[key] = value
    if geokeys.get(1024) != 2 or geokeys.get(2048) != 4326:
        raise RangeFetchError("Only geographic EPSG:4326 GeoTIFF is supported")
    if geokeys.get(1025) != 1:
        raise RangeFetchError("Only PixelIsArea GeoTIFF is supported")
    if any(k not in (1024, 1025, 2048) for k in geokeys):
        raise RangeFetchError("Unrecognized GeoKey requires review")
    transform = (sx, 0.0, lon - pixel_i * sx, 0.0, -sy, lat + pixel_j * sy)
    if not all(math.isfinite(v) for v in transform):
        raise RangeFetchError("Invalid derived affine transform")
    return {"crs": "EPSG:4326", "transform": transform, "pixel_is_area": True,
            "georeferencing_tags_parsed": True, "source_authenticated": False,
            "source_checksum_verified": False, "provenance_verified": False}
