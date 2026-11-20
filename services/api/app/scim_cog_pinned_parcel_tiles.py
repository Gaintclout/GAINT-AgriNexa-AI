"""ETag-pinned parcel tile transfer from a separately approved metadata plan.

The metadata plan is not version-pinned; therefore the caller must supply a
trusted plan and independently established strong ETag. This module verifies
the tile offsets and counts against the plan before returning compressed bytes.
"""
from .scim_cog_pinned_range_fetch import fetch_pinned_cog_range
from .scim_cog_object_version import validate_object_version
from .scim_cog_range_fetch import RangeFetchError, MAX_RANGE_BYTES
from .scim_cog_window_tiles import MAX_SELECTED_TILES, MAX_TRANSFER_BYTES

def fetch_pinned_parcel_tiles(url, plan, tiles, *, expected_etag,
                              expected_object_bytes, approved=False, opener=None):
    if not approved:
        raise RangeFetchError("Explicit parcel tile approval required")
    validate_object_version({"ETag":expected_etag},expected_etag=expected_etag)
    if type(expected_object_bytes) is not int or expected_object_bytes < 1:
        raise RangeFetchError("Invalid expected object size")
    indices = plan.get("tile_indices")
    if not isinstance(indices,list) or not 1 <= len(indices) <= MAX_SELECTED_TILES:
        raise RangeFetchError("Invalid planned tile selection")
    if len(tiles) != len(indices):
        raise RangeFetchError("Tile selection does not match plan")
    total=0
    for index,tile in zip(indices,tiles):
        if (type(index) is not int or type(tile.get("index")) is not int or
                tile["index"] != index or
                type(tile.get("offset")) is not int or
                type(tile.get("byte_count")) is not int):
            raise RangeFetchError("Tile metadata does not match plan")
        offset,size=tile["offset"],tile["byte_count"]
        if (offset < 8 or size < 1 or size > 8*1024*1024 or
                offset+size > expected_object_bytes):
            raise RangeFetchError("Tile outside object bounds")
        total+=size
        if total>MAX_TRANSFER_BYTES:
            raise RangeFetchError("Parcel tile transfer budget exceeded")
    payloads=[]
    for tile in tiles:
        offset,remaining=tile["offset"],tile["byte_count"]
        parts=[]
        while remaining:
            size=min(remaining,MAX_RANGE_BYTES)
            reply=fetch_pinned_cog_range(
                url,offset,size,expected_etag=expected_etag,
                approved=True,opener=opener)
            if reply["total_bytes"] != expected_object_bytes:
                raise RangeFetchError("Pinned object size changed")
            parts.append(reply["data"])
            offset+=size
            remaining-=size
        payloads.append({"index":tile["index"],"data":b"".join(parts)})
    return {"tiles":payloads,"tile_count":len(payloads),
            "tile_payload_bytes":total,"object_version_pinned":True,
            "metadata_version_pinned":False,"pixel_values_decoded":False,
            "source_checksum_verified":False,"provenance_verified":False}
