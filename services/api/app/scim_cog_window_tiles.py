"""Select and retrieve bounded TIFF tiles for an independently validated pixel window.

No geospatial transform is inferred: caller must establish parcel-to-pixel mapping
separately. Returned tile bytes are untrusted compressed data, not decoded pixels.
"""
from .scim_cog_tile_table import inspect_remote_tile_table
from .scim_cog_range_fetch import fetch_cog_range, RangeFetchError, MAX_RANGE_BYTES

MAX_SELECTED_TILES = 16
MAX_TRANSFER_BYTES = 16 * 1024 * 1024

def select_window_tiles(table: dict, *, col: int, row: int, width: int, height: int) -> list:
    """Choose tile records overlapping a half-open pixel rectangle."""
    if any(type(v) is not int for v in (col, row, width, height)):
        raise RangeFetchError("Pixel window must use integer coordinates")
    image_width, image_height = table["width"], table["height"]
    if (col < 0 or row < 0 or width < 1 or height < 1 or
            col + width > image_width or row + height > image_height):
        raise RangeFetchError("Pixel window outside image bounds")
    tw, th = table["tile_width"], table["tile_height"]
    columns = table["tile_columns"]
    left, right = col // tw, (col + width - 1) // tw
    top, bottom = row // th, (row + height - 1) // th
    selected_count = (right - left + 1) * (bottom - top + 1)
    if selected_count > MAX_SELECTED_TILES:
        raise RangeFetchError("Pixel window exceeds tile selection budget")
    tiles = table["tiles"]
    selected = []
    for tile_row in range(top, bottom + 1):
        for tile_col in range(left, right + 1):
            index = tile_row * columns + tile_col
            if index >= len(tiles) or tiles[index]["index"] != index:
                raise RangeFetchError("Invalid tile table ordering")
            selected.append(tiles[index])
    if sum(tile["byte_count"] for tile in selected) > MAX_TRANSFER_BYTES:
        raise RangeFetchError("Selected tile bytes exceed transfer budget")
    return selected

def fetch_window_tile_bytes(url: str, *, col: int, row: int, width: int,
                            height: int, approved: bool = False, opener=None) -> dict:
    """Fetch bounded tile payloads with strict HTTP 206 and object-size consistency."""
    if not approved:
        raise RangeFetchError("Explicit remote tile retrieval approval required")
    table = inspect_remote_tile_table(url, approved=approved, opener=opener)
    selected = select_window_tiles(table, col=col, row=row, width=width, height=height)
    payloads = []
    total_transferred = 0
    for tile in selected:
        chunks = []
        offset, remaining = tile["offset"], tile["byte_count"]
        while remaining:
            length = min(remaining, MAX_RANGE_BYTES)
            reply = fetch_cog_range(url, offset, length, approved=approved, opener=opener)
            if reply["total_bytes"] != table["object_bytes"]:
                raise RangeFetchError("Remote object size changed during tile retrieval")
            chunks.append(reply["data"])
            total_transferred += len(reply["data"])
            if total_transferred > MAX_TRANSFER_BYTES:
                raise RangeFetchError("Remote transfer budget exceeded")
            offset += length
            remaining -= length
        payloads.append({"index": tile["index"], "row": tile["row"],
                         "column": tile["column"], "data": b"".join(chunks)})
    return {"tiles": payloads, "tile_count": len(payloads),
            "tile_payload_bytes": total_transferred, "pixel_window": {
                "col": col, "row": row, "width": width, "height": height},
            "pixel_values_decoded": False, "parcel_georeferencing_verified": False,
            "source_checksum_verified": False, "provenance_verified": False}
