"""Read and validate classic TIFF decoding tags using bounded HTTP ranges.

This module does not infer compression or pixel format from tile payloads.
It accepts only scalar SHORT tags and a restricted single-band layout.
"""
from .scim_cog_header_probe import inspect_remote_tiff_header
from .scim_cog_range_fetch import fetch_cog_range, RangeFetchError

TAGS={258:"bits_per_sample",259:"compression",277:"samples_per_pixel",
      317:"predictor",339:"sample_format"}
DEFAULTS={"bits_per_sample":1,"compression":1,"samples_per_pixel":1,
          "predictor":1,"sample_format":1}
MAX_ENTRIES=128

def inspect_remote_decode_tags(url, *, approved=False, opener=None):
    if not approved:
        raise RangeFetchError("Explicit TIFF decode metadata approval required")
    header=inspect_remote_tiff_header(url,approved=True,opener=opener)
    if header["format"]!="TIFF":
        raise RangeFetchError("Only classic TIFF decoding metadata supported")
    total=header["object_bytes"]
    offset=header["first_ifd_offset"]
    order=header["byte_order"]
    count_result=fetch_cog_range(url,offset,2,approved=True,opener=opener)
    if count_result["total_bytes"]!=total:
        raise RangeFetchError("TIFF object size changed")
    count=int.from_bytes(count_result["data"],order)
    if not 1<=count<=MAX_ENTRIES or offset+2+12*count+4>total:
        raise RangeFetchError("Invalid TIFF directory bounds")
    result=fetch_cog_range(url,offset+2,12*count+4,approved=True,opener=opener)
    if result["total_bytes"]!=total:
        raise RangeFetchError("TIFF object size changed")
    values=dict(DEFAULTS)
    seen=set()
    for i in range(count):
        entry=result["data"][12*i:12*(i+1)]
        tag=int.from_bytes(entry[:2],order)
        if tag not in TAGS:
            continue
        if tag in seen:
            raise RangeFetchError("Duplicate TIFF decoding tag")
        seen.add(tag)
        kind=int.from_bytes(entry[2:4],order)
        n=int.from_bytes(entry[4:8],order)
        if kind!=3 or n!=1:
            raise RangeFetchError("Unsupported TIFF decoding tag type or count")
        values[TAGS[tag]]=int.from_bytes(entry[8:10],order)
    if (values["bits_per_sample"] not in (8,16)
            or values["compression"] not in (1,8,32946)
            or values["samples_per_pixel"]!=1
            or values["predictor"]!=1
            or values["sample_format"]!=1):
        raise RangeFetchError("Unsupported TIFF decoding metadata")
    return {**values,"byte_order":order,"object_bytes":total,
            "decode_tags_validated":True,"source_checksum_verified":False,
            "provenance_verified":False}
