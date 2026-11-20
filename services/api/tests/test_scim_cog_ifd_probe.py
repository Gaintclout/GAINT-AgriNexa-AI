"""Mocked bounded classic TIFF IFD metadata tests; no network."""
import pytest
from app import scim_cog_ifd_probe as probe
from app.scim_cog_range_fetch import RangeFetchError

URL = "https://sentinel-cogs.s3.us-west-2.amazonaws.com/sample.tif"

def make_tiff(*, width=512, height=256, entries=None):
    def entry(tag, value, kind=4, count=1):
        return (tag.to_bytes(2, "little") + kind.to_bytes(2, "little") +
                count.to_bytes(4, "little") + value.to_bytes(4, "little"))
    if entries is None:
        entries = [entry(256, width), entry(257, height), entry(322, 256),
                   entry(323, 256), entry(324, 300, count=2),
                   entry(325, 320, count=2)]
    offset = 16
    payload = bytearray(b"II" + (42).to_bytes(2, "little") +
                        offset.to_bytes(4, "little") + bytes(8))
    payload.extend(len(entries).to_bytes(2, "little"))
    for item in entries:
        payload.extend(item)
    payload.extend(bytes(4))
    payload.extend(bytes(max(0, 400 - len(payload))))
    return bytes(payload)

def install(monkeypatch, data):
    calls = []
    def header(url, *, approved=False, opener=None):
        assert approved
        return {"format": "TIFF", "byte_order": "little",
                "first_ifd_offset": 16, "object_bytes": len(data)}
    def fetch(url, start, length, *, approved=False, opener=None):
        assert approved and 0 < length <= 1048576
        calls.append((start, length))
        return {"data": data[start:start + length], "total_bytes": len(data)}
    monkeypatch.setattr(probe, "inspect_remote_tiff_header", header)
    monkeypatch.setattr(probe, "fetch_cog_range", fetch)
    return calls

def test_bounded_ifd_dimensions_and_tile_pointers(monkeypatch):
    calls = install(monkeypatch, make_tiff())
    result = probe.inspect_remote_classic_ifd(URL, approved=True)
    assert result["width"] == 512 and result["height"] == 256
    assert result["tile_arrays"]["tile_offsets"]["count"] == 2
    assert result["tile_arrays"]["tile_byte_counts"]["offset"] == 320
    assert result["tile_payload_verified"] is False
    assert calls == [(16, 2), (18, 76)]

def test_excessive_entry_count_rejected(monkeypatch):
    data = bytearray(make_tiff())
    data[16:18] = (129).to_bytes(2, "little")
    install(monkeypatch, bytes(data))
    with pytest.raises(RangeFetchError, match="entries"):
        probe.inspect_remote_classic_ifd(URL, approved=True)

def test_missing_height_rejected(monkeypatch):
    def entry(tag, value):
        return tag.to_bytes(2, "little") + (4).to_bytes(2, "little") + (1).to_bytes(4, "little") + value.to_bytes(4, "little")
    install(monkeypatch, make_tiff(entries=[entry(256, 512)]))
    with pytest.raises(RangeFetchError, match="dimensions"):
        probe.inspect_remote_classic_ifd(URL, approved=True)

def test_oversized_dimensions_rejected(monkeypatch):
    install(monkeypatch, make_tiff(width=100001))
    with pytest.raises(RangeFetchError, match="dimensions"):
        probe.inspect_remote_classic_ifd(URL, approved=True)

def test_object_size_change_rejected(monkeypatch):
    install(monkeypatch, make_tiff())
    original = probe.fetch_cog_range
    def changed(*args, **kwargs):
        result = original(*args, **kwargs)
        result["total_bytes"] += 1
        return result
    monkeypatch.setattr(probe, "fetch_cog_range", changed)
    with pytest.raises(RangeFetchError, match="changed"):
        probe.inspect_remote_classic_ifd(URL, approved=True)

def test_bigtiff_is_explicitly_unsupported(monkeypatch):
    monkeypatch.setattr(probe, "inspect_remote_tiff_header",
                        lambda *a, **kw: {"format": "BigTIFF"})
    with pytest.raises(RangeFetchError, match="BigTIFF"):
        probe.inspect_remote_classic_ifd(URL, approved=True)
