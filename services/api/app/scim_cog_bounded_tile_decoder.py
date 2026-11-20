"""Strict, memory-bounded decoder for an explicitly declared TIFF tile subset.

Supports only 8/16-bit single-band integer tiles with no predictor and
compression NONE or zlib DEFLATE. The caller must obtain the TIFF sample
format, compression, and predictor from validated metadata; do not infer
them from tile bytes. This is not a general GeoTIFF decoder.
"""
import zlib
from .scim_cog_range_fetch import RangeFetchError

MAX_DECODED_TILE_BYTES=8*1024*1024

def decode_integer_tile(payload, *, width, height, bits_per_sample,
                        compression, byte_order="little", samples_per_pixel=1,
                        sample_format=1, predictor=1):
    if type(width) is not int or type(height) is not int or not (1<=width<=4096 and 1<=height<=4096):
        raise RangeFetchError("Invalid tile dimensions")
    if bits_per_sample not in (8,16) or type(bits_per_sample) is not int:
        raise RangeFetchError("Unsupported sample bit depth")
    if compression not in (1,8,32946) or type(compression) is not int:
        raise RangeFetchError("Unsupported TIFF compression")
    if byte_order not in ("little","big"):
        raise RangeFetchError("Invalid TIFF byte order")
    if samples_per_pixel != 1 or sample_format != 1 or predictor != 1:
        raise RangeFetchError("Unsupported TIFF sample layout or predictor")
    if not isinstance(payload,bytes):
        raise RangeFetchError("Tile payload must be bytes")
    expected=width*height*(bits_per_sample//8)
    if expected>MAX_DECODED_TILE_BYTES:
        raise RangeFetchError("Decoded tile exceeds memory budget")
    if compression==1:
        if len(payload)!=expected:
            raise RangeFetchError("Uncompressed tile length mismatch")
        raw=payload
    else:
        decompressor=zlib.decompressobj()
        try:
            raw=decompressor.decompress(payload,expected+1)
            if len(raw)!=expected or not decompressor.eof or decompressor.unused_data or decompressor.unconsumed_tail:
                raise RangeFetchError("Invalid or excessive compressed tile")
            raw+=decompressor.flush()
        except zlib.error as exc:
            raise RangeFetchError("Invalid DEFLATE tile") from exc
        if len(raw)!=expected:
            raise RangeFetchError("Decoded tile length mismatch")
    step=bits_per_sample//8
    pixels=[int.from_bytes(raw[i:i+step],byte_order)
            for i in range(0,expected,step)]
    return {"width":width,"height":height,"pixels":pixels,
            "pixel_count":len(pixels),"decoded_bytes":expected,
            "compression":compression,"sample_format":"unsigned_integer",
            "source_checksum_verified":False,"provenance_verified":False}
