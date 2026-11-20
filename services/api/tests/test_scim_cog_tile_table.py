"""No-network tests for bounded classic TIFF tile offset/count tables."""
import pytest
from app import scim_cog_tile_table as module
from app.scim_cog_range_fetch import RangeFetchError

URL = "https://sentinel-cogs.s3.us-west-2.amazonaws.com/sample.tif"

def setup(monkeypatch, offsets=(100, 200), sizes=(20, 30), *, total=500,
          count=2, inline=False):
    arrays = {"tile_offsets": {"count": count, "offset": 16, "type": 4, "inline": inline},
              "tile_byte_counts": {"count": count, "offset": 32, "type": 4, "inline": inline}}
    meta = {"width": 512, "height": 256, "tile_width": 256, "tile_height": 256,
            "byte_order": "little", "tile_arrays": arrays, "object_bytes": total}
    monkeypatch.setattr(module, "inspect_remote_classic_ifd",
                        lambda *args, **kwargs: meta)
    calls = []
    def fetch(url, start, length, *, approved=False, opener=None):
        assert approved
        calls.append((start, length))
        values = offsets if start == 16 else sizes
        return {"data": b"".join(v.to_bytes(4, "little") for v in values),
                "total_bytes": total}
    monkeypatch.setattr(module, "fetch_cog_range", fetch)
    return calls

def test_tile_grid_and_ranges(monkeypatch):
    calls = setup(monkeypatch)
    result = module.inspect_remote_tile_table(URL, approved=True)
    assert [(tile["offset"], tile["byte_count"]) for tile in result["tiles"]] == [(100, 20), (200, 30)]
    assert result["tile_columns"] == 2 and result["tile_rows"] == 1
    assert result["tile_ranges_verified"] is True
    assert result["tile_payload_verified"] is False
    assert calls == [(16, 8), (32, 8)]

def test_approval_required(monkeypatch):
    calls = setup(monkeypatch)
    with pytest.raises(RangeFetchError, match="approval"):
        module.inspect_remote_tile_table(URL)
    assert calls == []

@pytest.mark.parametrize("offsets,sizes", [
    ((490, 200), (20, 30)),
    ((100, 200), (0, 30)),
    ((0, 200), (20, 30)),
    ((100, 200), (9000000, 30)),
])
def test_bad_tile_ranges_rejected(monkeypatch, offsets, sizes):
    setup(monkeypatch, offsets, sizes)
    with pytest.raises(RangeFetchError, match="Tile range"):
        module.inspect_remote_tile_table(URL, approved=True)

def test_count_mismatch_rejected(monkeypatch):
    setup(monkeypatch, count=3)
    with pytest.raises(RangeFetchError, match="count"):
        module.inspect_remote_tile_table(URL, approved=True)

def test_inline_tables_fail_closed(monkeypatch):
    setup(monkeypatch, inline=True)
    with pytest.raises(RangeFetchError, match="Inline"):
        module.inspect_remote_tile_table(URL, approved=True)

def test_object_size_change_rejected(monkeypatch):
    setup(monkeypatch)
    original = module.fetch_cog_range
    def changed(*args, **kwargs):
        response = original(*args, **kwargs)
        response["total_bytes"] += 1
        return response
    monkeypatch.setattr(module, "fetch_cog_range", changed)
    with pytest.raises(RangeFetchError, match="changed"):
        module.inspect_remote_tile_table(URL, approved=True)
