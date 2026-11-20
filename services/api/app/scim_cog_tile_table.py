"""Bounded remote TIFF tile-table inspection; metadata only, never tile payloads."""
from .scim_cog_ifd_probe import inspect_remote_classic_ifd
from .scim_cog_range_fetch import fetch_cog_range, RangeFetchError, MAX_RANGE_BYTES

MAX_TILES = 4096
MAX_TILE_BYTES = 8 * 1024 * 1024
MAX_TABLE_BYTES = 32768

def inspect_remote_tile_table(url: str, *, approved: bool = False, opener=None) -> dict:
    """Validate offset/count pairs for a tiled classic TIFF.

    Requires external arrays; inline arrays fail closed until inline values are exposed
    by the IFD parser. This is not proof of a compliant COG or valid compressed tiles.
    """
    if not approved:
        raise RangeFetchError("Explicit remote range approval required")
    meta = inspect_remote_classic_ifd(url, approved=approved, opener=opener)
    width, height = meta["width"], meta["height"]
    tile_width, tile_height = meta["tile_width"], meta["tile_height"]
    arrays = meta["tile_arrays"]
    if not tile_width or not tile_height or set(arrays) != {"tile_offsets", "tile_byte_counts"}:
        raise RangeFetchError("Tiled TIFF metadata required")
    columns = (width + tile_width - 1) // tile_width
    rows = (height + tile_height - 1) // tile_height
    expected = columns * rows
    if expected < 1 or expected > MAX_TILES:
        raise RangeFetchError("Tile count exceeds inspection budget")
    if any(arrays[key]["count"] != expected for key in arrays):
        raise RangeFetchError("Tile array count does not match image grid")
    if any(arrays[key]["inline"] for key in arrays):
        raise RangeFetchError("Inline tile tables not yet supported")
    total = meta.get("object_bytes")
    # IFD parser does not currently return object size; establish one from first range
    # and require identical size for all subsequent reads.
    observed_total = None
    decoded = {}
    for key in ("tile_offsets", "tile_byte_counts"):
        item = arrays[key]
        element_size = {3: 2, 4: 4}.get(item["type"])
        if element_size is None:
            raise RangeFetchError("Unsupported tile table type")
        size = expected * element_size
        if size > MAX_TABLE_BYTES:
            raise RangeFetchError("Tile table exceeds inspection budget")
        offset = item["offset"]
        chunks = []
        for position in range(0, size, MAX_RANGE_BYTES):
            length = min(MAX_RANGE_BYTES, size - position)
            result = fetch_cog_range(url, offset + position, length,
                                     approved=approved, opener=opener)
            if observed_total is None:
                observed_total = result["total_bytes"]
            if result["total_bytes"] != observed_total:
                raise RangeFetchError("Object size changed during tile inspection")
            chunks.append(result["data"])
        raw = b"".join(chunks)
        decoded[key] = [int.from_bytes(raw[i:i + element_size], meta["byte_order"])
                        for i in range(0, size, element_size)]
    if total is not None and observed_total != total:
        raise RangeFetchError("Object size changed after IFD inspection")
    tiles = []
    for index, (offset, size) in enumerate(zip(decoded["tile_offsets"],
                                                decoded["tile_byte_counts"])):
        if size == 0 and offset == 0:
            raise RangeFetchError("Sparse tiles are not supported")
        if offset < 8 or size < 1 or size > MAX_TILE_BYTES or offset + size > observed_total:
            raise RangeFetchError("Tile range outside object or byte budget")
        tiles.append({"index": index, "row": index // columns, "column": index % columns,
                      "offset": offset, "byte_count": size})
    return {"width": width, "height": height, "tile_width": tile_width,
            "tile_height": tile_height, "tile_rows": rows, "tile_columns": columns,
            "tiles": tiles, "object_bytes": observed_total, "tile_ranges_verified": True,
            "tile_payload_verified": False, "cog_layout_verified": False,
            "source_checksum_verified": False, "provenance_verified": False}
