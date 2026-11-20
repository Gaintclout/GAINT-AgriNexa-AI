"""Decode previously retrieved ETag-pinned TIFF tiles using verified decode tags.

Both metadata and tile payloads must be supplied from the same trusted pinned
retrieval workflow. This function performs no network access, masking, or
provenance verification. It refuses oversized multi-tile decoding jobs.
"""
from .scim_cog_bounded_tile_decoder import decode_integer_tile, MAX_DECODED_TILE_BYTES
from .scim_cog_range_fetch import RangeFetchError

MAX_DECODE_JOB_BYTES=16*1024*1024
MAX_DECODE_JOB_TILES=16

def decode_pinned_parcel_tiles(retrieval, table, decode_tags):
    if not isinstance(retrieval,dict) or not isinstance(table,dict) or not isinstance(decode_tags,dict):
        raise RangeFetchError("Invalid pinned parcel decode inputs")
    if (retrieval.get("object_version_pinned") is not True or
            retrieval.get("metadata_version_pinned") is not True or
            decode_tags.get("decode_tags_validated") is not True):
        raise RangeFetchError("Pinned retrieval and validated decode tags required")
    if decode_tags.get("object_bytes") != table.get("object_bytes"):
        raise RangeFetchError("Decode metadata object size mismatch")
    tw,th=table.get("tile_width"),table.get("tile_height")
    bits=decode_tags.get("bits_per_sample")
    if (type(tw) is not int or type(th) is not int or
            not 1<=tw<=4096 or not 1<=th<=4096 or
            type(bits) is not int or bits not in (8,16)):
        raise RangeFetchError("Invalid decoded tile geometry")
    expected=tw*th*(bits//8)
    if expected>MAX_DECODED_TILE_BYTES:
        raise RangeFetchError("Decoded tile exceeds memory budget")
    tiles=retrieval.get("tiles")
    if not isinstance(tiles,list) or not 1<=len(tiles)<=MAX_DECODE_JOB_TILES:
        raise RangeFetchError("Invalid decoded tile count")
    if expected*len(tiles)>MAX_DECODE_JOB_BYTES:
        raise RangeFetchError("Decoded parcel exceeds memory budget")
    metadata_tiles=table.get("tiles")
    if not isinstance(metadata_tiles,list):
        raise RangeFetchError("Missing TIFF tile table")
    decoded=[]
    seen=set()
    for tile in tiles:
        if not isinstance(tile,dict) or type(tile.get("index")) is not int:
            raise RangeFetchError("Invalid retrieved tile")
        index=tile["index"]
        if index in seen or index<0 or index>=len(metadata_tiles):
            raise RangeFetchError("Duplicate or invalid retrieved tile index")
        seen.add(index)
        metadata=metadata_tiles[index]
        if metadata.get("index")!=index:
            raise RangeFetchError("Tile index mismatch")
        data=tile.get("data")
        if not isinstance(data,bytes) or len(data)!=metadata.get("byte_count"):
            raise RangeFetchError("Tile byte count mismatch")
        result=decode_integer_tile(data,width=tw,height=th,
            bits_per_sample=bits,compression=decode_tags["compression"],
            byte_order=decode_tags["byte_order"],
            samples_per_pixel=decode_tags["samples_per_pixel"],
            sample_format=decode_tags["sample_format"],
            predictor=decode_tags["predictor"])
        decoded.append({"index":index,"row":metadata["row"],
                        "column":metadata["column"],"pixels":result["pixels"]})
    return {"tiles":decoded,"tile_count":len(decoded),
            "decoded_bytes":expected*len(decoded),"pixel_values_decoded":True,
            "parcel_mask_applied":False,"source_checksum_verified":False,
            "provenance_verified":False}
