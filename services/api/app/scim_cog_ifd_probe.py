"""Bounded classic TIFF first-IFD parser for trusted remote COG metadata.

Does not fetch image tiles, validate COG layout, or certify provenance.
BigTIFF directories are intentionally unsupported until separately implemented.
"""
from .scim_cog_header_probe import inspect_remote_tiff_header
from .scim_cog_range_fetch import fetch_cog_range, RangeFetchError

MAX_IFD_ENTRIES = 128
MAX_IFD_BYTES = 2 + 12 * MAX_IFD_ENTRIES + 4
MAX_DIMENSION = 100000
MAX_PIXELS = 1000000000
TAGS = {256: "width", 257: "height", 322: "tile_width", 323: "tile_height",
        324: "tile_offsets", 325: "tile_byte_counts"}
TYPE_SIZES = {3: 2, 4: 4}

def inspect_remote_classic_ifd(url: str, *, approved: bool = False, opener=None) -> dict:
    """Read first classic TIFF IFD, accepting only inline scalar dimension tags.

    Tile offset/count arrays are identified but not dereferenced or trusted.
    """
    header = inspect_remote_tiff_header(url, approved=approved, opener=opener)
    if header["format"] != "TIFF":
        raise RangeFetchError("BigTIFF IFD parsing is not supported")
    offset = header["first_ifd_offset"]
    total = header["object_bytes"]
    if offset + 2 > total:
        raise RangeFetchError("IFD entry count is outside object")
    count_reply = fetch_cog_range(url, offset, 2, approved=approved, opener=opener)
    if count_reply["total_bytes"] != total:
        raise RangeFetchError("Object size changed during inspection")
    order = header["byte_order"]
    count = int.from_bytes(count_reply["data"], order)
    if count == 0 or count > MAX_IFD_ENTRIES:
        raise RangeFetchError("Invalid or excessive IFD entries")
    length = count * 12 + 4
    if length > MAX_IFD_BYTES or offset + 2 + length > total:
        raise RangeFetchError("IFD exceeds allowed bounds")
    reply = fetch_cog_range(url, offset + 2, length, approved=approved, opener=opener)
    if reply["total_bytes"] != total:
        raise RangeFetchError("Object size changed during inspection")
    raw = reply["data"]
    fields = {}
    tile_array_tags = {}
    for index in range(count):
        entry = raw[index * 12:(index + 1) * 12]
        tag = int.from_bytes(entry[:2], order)
        if tag not in TAGS:
            continue
        if tag in fields or tag in tile_array_tags:
            raise RangeFetchError("Duplicate critical TIFF tag")
        field_type = int.from_bytes(entry[2:4], order)
        item_count = int.from_bytes(entry[4:8], order)
        if field_type not in TYPE_SIZES or item_count < 1:
            raise RangeFetchError("Unsupported critical TIFF tag type")
        byte_count = TYPE_SIZES[field_type] * item_count
        if tag in (324, 325):
            if item_count > MAX_PIXELS:
                raise RangeFetchError("Excessive tile array entries")
            if byte_count > 4:
                pointer = int.from_bytes(entry[8:12], order)
                if pointer < 8 or pointer + byte_count > total:
                    raise RangeFetchError("Tile array pointer outside object")
                tile_array_tags[TAGS[tag]] = {"count": item_count, "offset": pointer,
                                               "type": field_type, "inline": False}
            else:
                tile_array_tags[TAGS[tag]] = {"count": item_count, "inline": True,
                                               "type": field_type}
            continue
        if item_count != 1:
            raise RangeFetchError("Non-scalar dimension tag")
        fields[TAGS[tag]] = int.from_bytes(entry[8:8 + byte_count], order)
    for name in ("width", "height"):
        if name not in fields or not 1 <= fields[name] <= MAX_DIMENSION:
            raise RangeFetchError("Missing or invalid TIFF dimensions")
    if fields["width"] * fields["height"] > MAX_PIXELS:
        raise RangeFetchError("Excessive TIFF pixel count")
    if ("tile_width" in fields) != ("tile_height" in fields):
        raise RangeFetchError("Incomplete tile dimensions")
    if "tile_width" in fields:
        if not 1 <= fields["tile_width"] <= MAX_DIMENSION or not 1 <= fields["tile_height"] <= MAX_DIMENSION:
            raise RangeFetchError("Invalid tile dimensions")
    if ("tile_offsets" in tile_array_tags) != ("tile_byte_counts" in tile_array_tags):
        raise RangeFetchError("Incomplete tile offset metadata")
    if tile_array_tags and tile_array_tags["tile_offsets"]["count"] != tile_array_tags["tile_byte_counts"]["count"]:
        raise RangeFetchError("Mismatched tile array counts")
    return {"format": "TIFF", "byte_order": order, "width": fields["width"],
            "height": fields["height"], "tile_width": fields.get("tile_width"),
            "tile_height": fields.get("tile_height"), "tile_arrays": tile_array_tags,
            "ifd_entries": count, "object_bytes": total, "ifd_bounds_verified": True,
            "tile_payload_verified": False, "cog_layout_verified": False,
            "source_checksum_verified": False, "provenance_verified": False}
