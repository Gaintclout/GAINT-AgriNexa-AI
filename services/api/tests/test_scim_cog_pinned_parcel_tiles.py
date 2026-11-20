import pytest
from app import scim_cog_pinned_parcel_tiles as module
from app.scim_cog_range_fetch import RangeFetchError

URL="https://sentinel-cogs.s3.us-west-2.amazonaws.com/synthetic.tif"
PLAN={"tile_indices":[2,3]}
TILES=[{"index":2,"offset":100,"byte_count":3},
       {"index":3,"offset":200,"byte_count":2}]
ETAG='"scene-v1"'

def test_pinned_parcel_tiles(monkeypatch):
    calls=[]
    def fetch(url,offset,length,**kwargs):
        calls.append((offset,length,kwargs["expected_etag"]))
        return {"data":b"x"*length,"total_bytes":1000}
    monkeypatch.setattr(module,"fetch_pinned_cog_range",fetch)
    result=module.fetch_pinned_parcel_tiles(
        URL,PLAN,TILES,expected_etag=ETAG,expected_object_bytes=1000,approved=True)
    assert calls==[(100,3,ETAG),(200,2,ETAG)]
    assert result["tile_payload_bytes"]==5
    assert result["metadata_version_pinned"] is False
    assert result["source_checksum_verified"] is False

def test_approval_before_io(monkeypatch):
    monkeypatch.setattr(module,"fetch_pinned_cog_range",
                        lambda *a,**k:pytest.fail("network call"))
    with pytest.raises(RangeFetchError,match="approval"):
        module.fetch_pinned_parcel_tiles(
            URL,PLAN,TILES,expected_etag=ETAG,expected_object_bytes=1000)

@pytest.mark.parametrize("tiles",[
    [{"index":3,"offset":100,"byte_count":3},{"index":2,"offset":200,"byte_count":2}],
    [{"index":2,"offset":100,"byte_count":3}],
    [{"index":2,"offset":999,"byte_count":3},{"index":3,"offset":200,"byte_count":2}],
    [{"index":2,"offset":100,"byte_count":0},{"index":3,"offset":200,"byte_count":2}]])
def test_bad_tile_metadata_rejected(monkeypatch,tiles):
    monkeypatch.setattr(module,"fetch_pinned_cog_range",
                        lambda *a,**k:pytest.fail("network call"))
    with pytest.raises(RangeFetchError):
        module.fetch_pinned_parcel_tiles(
            URL,PLAN,tiles,expected_etag=ETAG,expected_object_bytes=1000,approved=True)

def test_object_size_changed(monkeypatch):
    monkeypatch.setattr(module,"fetch_pinned_cog_range",
                        lambda *a,**k:{"data":b"x"*a[2],"total_bytes":1001})
    with pytest.raises(RangeFetchError,match="size changed"):
        module.fetch_pinned_parcel_tiles(
            URL,PLAN,TILES,expected_etag=ETAG,expected_object_bytes=1000,approved=True)
