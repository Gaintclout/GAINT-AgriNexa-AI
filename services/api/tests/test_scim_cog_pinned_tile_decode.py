"""Offline integration tests for pinned tile results and bounded decoding."""
import zlib
import pytest
from app.scim_cog_pinned_tile_decode import decode_pinned_parcel_tiles
from app.scim_cog_range_fetch import RangeFetchError

def sample(*,compressed=True):
    raw=b"\x01\x00\x02\x00\x03\x00\x04\x00"
    data=zlib.compress(raw) if compressed else raw
    table={"object_bytes":256,"tile_width":2,"tile_height":2,
           "tiles":[{"index":0,"row":0,"column":0,"byte_count":len(data)}]}
    tags={"decode_tags_validated":True,"object_bytes":256,
          "bits_per_sample":16,"compression":8 if compressed else 1,
          "byte_order":"little","samples_per_pixel":1,"sample_format":1,"predictor":1}
    retrieval={"object_version_pinned":True,"metadata_version_pinned":True,
               "tiles":[{"index":0,"data":data}]}
    return retrieval,table,tags

@pytest.mark.parametrize("compressed",[True,False])
def test_decodes_verified_tile_payload(compressed):
    result=decode_pinned_parcel_tiles(*sample(compressed=compressed))
    assert result["tiles"][0]["pixels"]==[1,2,3,4]
    assert result["decoded_bytes"]==8
    assert result["pixel_values_decoded"] is True
    assert result["parcel_mask_applied"] is False

def test_rejects_unpinned_retrieval():
    retrieval,table,tags=sample()
    retrieval["metadata_version_pinned"]=False
    with pytest.raises(RangeFetchError,match="Pinned"):
        decode_pinned_parcel_tiles(retrieval,table,tags)

def test_rejects_unvalidated_tags():
    retrieval,table,tags=sample()
    tags["decode_tags_validated"]=False
    with pytest.raises(RangeFetchError):
        decode_pinned_parcel_tiles(retrieval,table,tags)

def test_rejects_object_size_mismatch():
    retrieval,table,tags=sample()
    tags["object_bytes"]=257
    with pytest.raises(RangeFetchError,match="size"):
        decode_pinned_parcel_tiles(retrieval,table,tags)

def test_rejects_tile_length_mismatch():
    retrieval,table,tags=sample()
    retrieval["tiles"][0]["data"]=b"short"
    with pytest.raises(RangeFetchError,match="byte count"):
        decode_pinned_parcel_tiles(retrieval,table,tags)

def test_rejects_duplicate_tiles():
    retrieval,table,tags=sample()
    retrieval["tiles"].append(dict(retrieval["tiles"][0]))
    with pytest.raises(RangeFetchError,match="Duplicate"):
        decode_pinned_parcel_tiles(retrieval,table,tags)

def test_rejects_oversized_decode_job():
    retrieval,table,tags=sample()
    table["tile_width"]=4096
    table["tile_height"]=4096
    with pytest.raises(RangeFetchError,match="budget"):
        decode_pinned_parcel_tiles(retrieval,table,tags)
