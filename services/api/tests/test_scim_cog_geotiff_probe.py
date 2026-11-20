"""Mocked GeoTIFF georeferencing parser tests; no live network."""
import struct
import pytest
from app import scim_cog_geotiff_probe as module
from app.scim_cog_range_fetch import RangeFetchError

URL = "https://sentinel-cogs.s3.us-west-2.amazonaws.com/test.tif"

def build(*, epsg=4326, raster_type=1, scale=(.01, .01, 0), extra_keys=()):
    keys = [1, 1, 0, 3 + len(extra_keys), 1024, 0, 1, 2,
            1025, 0, 1, raster_type, 2048, 0, 1, epsg]
    for key in extra_keys:
        keys.extend(key)
    fields = [(33550, 12, 3, struct.pack("<3d", *scale)),
              (33922, 12, 6, struct.pack("<6d", 0, 0, 0, 80, 20, 0)),
              (34735, 3, len(keys), struct.pack("<" + "H" * len(keys), *keys))]
    payload = bytearray(512)
    payload[:8] = b"II" + struct.pack("<HI", 42, 16)
    struct.pack_into("<H", payload, 16, len(fields))
    cursor = 128
    for index, (tag, kind, count, raw) in enumerate(fields):
        struct.pack_into("<HHII", payload, 18 + index * 12, tag, kind, count, cursor)
        payload[cursor:cursor + len(raw)] = raw
        cursor += len(raw)
    return bytes(payload)

def install(monkeypatch, data):
    monkeypatch.setattr(module, "inspect_remote_tiff_header", lambda *a, **kw: {
        "format": "TIFF", "byte_order": "little", "first_ifd_offset": 16,
        "object_bytes": len(data)})
    calls = []
    def fetch(url, start, length, *, approved=False, opener=None):
        assert approved
        calls.append((start, length))
        return {"data": data[start:start + length], "total_bytes": len(data)}
    monkeypatch.setattr(module, "fetch_cog_range", fetch)
    return calls

def test_epsg4326_grid_parsed(monkeypatch):
    calls = install(monkeypatch, build())
    result = module.inspect_remote_geotiff_grid(URL, approved=True)
    assert result["crs"] == "EPSG:4326"
    assert result["transform"] == pytest.approx((.01, 0, 80, 0, -.01, 20))
    assert not result["source_authenticated"]
    assert len(calls) == 5

def test_approval_gate(monkeypatch):
    calls = install(monkeypatch, build())
    with pytest.raises(RangeFetchError, match="approval"):
        module.inspect_remote_geotiff_grid(URL)
    assert calls == []

@pytest.mark.parametrize("kwargs", [
    {"epsg": 3857}, {"raster_type": 2}, {"scale": (0, .01, 0)},
    {"extra_keys": [(3072, 0, 1, 32644)]},
])
def test_unsupported_georeferencing_rejected(monkeypatch, kwargs):
    install(monkeypatch, build(**kwargs))
    with pytest.raises(RangeFetchError):
        module.inspect_remote_geotiff_grid(URL, approved=True)

def test_truncated_tag_pointer_rejected(monkeypatch):
    data = bytearray(build())
    struct.pack_into("<I", data, 18 + 8, 500)
    install(monkeypatch, bytes(data))
    with pytest.raises(RangeFetchError, match="outside"):
        module.inspect_remote_geotiff_grid(URL, approved=True)
