"""Mocked SCIM pixel-window tile retrieval tests, no live network."""
import pytest
from app import scim_cog_window_tiles as module
from app.scim_cog_range_fetch import RangeFetchError

URL = "https://sentinel-cogs.s3.us-west-2.amazonaws.com/test.tif"

def table():
    return {"width": 512, "height": 512, "tile_width": 256, "tile_height": 256,
            "tile_columns": 2, "object_bytes": 1000,
            "tiles": [{"index": i, "row": i // 2, "column": i % 2,
                       "offset": 100 + 100 * i, "byte_count": 4}
                      for i in range(4)]}

def test_select_single_tile():
    assert [x["index"] for x in module.select_window_tiles(
        table(), col=0, row=0, width=100, height=100)] == [0]

def test_select_crossing_tile_boundaries():
    assert [x["index"] for x in module.select_window_tiles(
        table(), col=250, row=250, width=20, height=20)] == [0, 1, 2, 3]

@pytest.mark.parametrize("window", [
    (-1, 0, 1, 1), (0, 0, 0, 1), (500, 0, 20, 1),
    (0, 500, 1, 20), (True, 0, 1, 1),
])
def test_invalid_pixel_window_rejected(window):
    with pytest.raises(RangeFetchError):
        module.select_window_tiles(table(), col=window[0], row=window[1],
                                   width=window[2], height=window[3])

def test_retrieves_exact_selected_tile_bytes(monkeypatch):
    monkeypatch.setattr(module, "inspect_remote_tile_table", lambda *a, **kw: table())
    calls = []
    def fetch(url, start, length, *, approved=False, opener=None):
        assert approved
        calls.append((start, length))
        return {"data": b"abcd", "total_bytes": 1000}
    monkeypatch.setattr(module, "fetch_cog_range", fetch)
    result = module.fetch_window_tile_bytes(URL, col=0, row=0, width=20, height=20,
                                            approved=True)
    assert calls == [(100, 4)]
    assert result["tiles"][0]["data"] == b"abcd"
    assert result["pixel_values_decoded"] is False

def test_no_approval_no_network(monkeypatch):
    calls = []
    monkeypatch.setattr(module, "inspect_remote_tile_table", lambda *a, **kw: calls.append(1))
    with pytest.raises(RangeFetchError, match="approval"):
        module.fetch_window_tile_bytes(URL, col=0, row=0, width=1, height=1)
    assert not calls

def test_object_size_change_fails_closed(monkeypatch):
    monkeypatch.setattr(module, "inspect_remote_tile_table", lambda *a, **kw: table())
    monkeypatch.setattr(module, "fetch_cog_range",
                        lambda *a, **kw: {"data": b"abcd", "total_bytes": 999})
    with pytest.raises(RangeFetchError, match="changed"):
        module.fetch_window_tile_bytes(URL, col=0, row=0, width=1, height=1,
                                       approved=True)

def test_transfer_budget_checked_before_network():
    info = table()
    info["tiles"][0]["byte_count"] = module.MAX_TRANSFER_BYTES + 1
    with pytest.raises(RangeFetchError, match="budget"):
        module.select_window_tiles(info, col=0, row=0, width=1, height=1)
