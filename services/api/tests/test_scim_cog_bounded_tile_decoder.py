"""Bounded TIFF tile decoder regression tests; offline and deterministic."""
import zlib
import pytest
from app.scim_cog_bounded_tile_decoder import decode_integer_tile
from app.scim_cog_range_fetch import RangeFetchError

def test_uncompressed_uint16_little_endian():
    result=decode_integer_tile(b"\x01\x00\x00\x01\xff\xff\x00\x00",
        width=2,height=2,bits_per_sample=16,compression=1)
    assert result["pixels"]==[1,256,65535,0]
    assert result["pixel_count"]==4
    assert result["source_checksum_verified"] is False

def test_deflate_uint16_big_endian():
    data=b"\x00\x01\x01\x00\xff\xff\x00\x00"
    result=decode_integer_tile(zlib.compress(data),width=2,height=2,
        bits_per_sample=16,compression=8,byte_order="big")
    assert result["pixels"]==[1,256,65535,0]

def test_deflate_uint8():
    result=decode_integer_tile(zlib.compress(b"\x01\x02\x03\x04"),
        width=2,height=2,bits_per_sample=8,compression=32946)
    assert result["pixels"]==[1,2,3,4]

@pytest.mark.parametrize("changes",[
    {"compression":5},{"bits_per_sample":32},{"predictor":2},
    {"samples_per_pixel":3},{"sample_format":2},{"width":5000},
    {"height":5000},{"byte_order":"unknown"}])
def test_unsupported_layout_rejected(changes):
    args=dict(width=2,height=2,bits_per_sample=8,compression=1)
    args.update(changes)
    with pytest.raises(RangeFetchError):
        decode_integer_tile(b"1234",**args)

def test_uncompressed_wrong_length_rejected():
    with pytest.raises(RangeFetchError,match="length"):
        decode_integer_tile(b"123",width=2,height=2,bits_per_sample=8,compression=1)

def test_compressed_expansion_bomb_rejected():
    payload=zlib.compress(b"X"*20000)
    with pytest.raises(RangeFetchError):
        decode_integer_tile(payload,width=2,height=2,bits_per_sample=8,compression=8)

def test_trailing_compressed_data_rejected():
    payload=zlib.compress(b"abcd")+b"unexpected"
    with pytest.raises(RangeFetchError):
        decode_integer_tile(payload,width=2,height=2,bits_per_sample=8,compression=8)

def test_truncated_compressed_data_rejected():
    payload=zlib.compress(b"abcd")[:-2]
    with pytest.raises(RangeFetchError):
        decode_integer_tile(payload,width=2,height=2,bits_per_sample=8,compression=8)

def test_memory_limit_rejected_before_decompression():
    with pytest.raises(RangeFetchError,match="budget"):
        decode_integer_tile(b"",width=4096,height=4096,bits_per_sample=16,compression=8)
