"""Offline synthetic Classic GeoTIFF UTM metadata tests; no network."""
import struct
import pytest
from app import scim_cog_projected_grid_probe as probe
from app.scim_cog_range_fetch import RangeFetchError

URL = "https://sentinel-cogs.s3.us-west-2.amazonaws.com/synthetic.tif"

def fixture(*, epsg=32644, model=1, scale=(10.,10.,0.), bad_pointer=False,
            duplicate=False, missing=False, big_endian=False):
    order = ">" if big_endian else "<"
    keys = (1,1,0,3,1024,0,1,model,1025,0,1,1,3072,0,1,epsg)
    fields = [(33550,12,3,struct.pack(order+"3d",*scale)),
              (33922,12,6,struct.pack(order+"6d",0,0,0,500000,2000000,0)),
              (34735,3,len(keys),struct.pack(order+"16H",*keys))]
    if missing:
        fields.pop()
    if duplicate:
        fields.append(fields[0])
    buf = bytearray(512)
    buf[:2] = b"MM" if big_endian else b"II"
    struct.pack_into(order+"HI",buf,2,42,16)
    struct.pack_into(order+"H",buf,16,len(fields))
    pos = 160
    for i,(tag,kind,count,data) in enumerate(fields):
        ptr = 510 if bad_pointer and tag == 34735 else pos
        struct.pack_into(order+"HHII",buf,18+12*i,tag,kind,count,ptr)
        buf[pos:pos+len(data)] = data
        pos += len(data)
    return bytes(buf)

def patch(monkeypatch, data, *, changed_size=False, truncated=False):
    calls = []
    monkeypatch.setattr(probe,"inspect_remote_tiff_header",lambda *args,**kwargs:{
        "format":"TIFF","byte_order":"big" if data[:2]==b"MM" else "little",
        "object_bytes":len(data),"first_ifd_offset":16})
    def fetch(url,start,length,*,approved=False,opener=None):
        assert approved
        calls.append((start,length))
        payload = data[start:start+length]
        if truncated:
            payload = payload[:-1]
        return {"data":payload,"total_bytes":len(data)+(1 if changed_size else 0)}
    monkeypatch.setattr(probe,"fetch_cog_range",fetch)
    return calls

@pytest.mark.parametrize("big_endian",[False,True])
def test_utm44_grid(monkeypatch,big_endian):
    calls = patch(monkeypatch,fixture(big_endian=big_endian))
    result = probe.inspect_remote_projected_grid(URL,approved=True)
    assert result["crs"]=="EPSG:32644"
    assert result["transform"]==pytest.approx((10,0,500000,0,-10,2000000))
    assert result["source_authenticated"] is False
    assert len(calls)==5

def test_approval_blocks_reads(monkeypatch):
    calls=patch(monkeypatch,fixture())
    with pytest.raises(RangeFetchError,match="approval"):
        probe.inspect_remote_projected_grid(URL)
    assert calls==[]

@pytest.mark.parametrize("kwargs",[
    {"epsg":3857},{"model":2},{"scale":(0.,10.,0.)},
    {"bad_pointer":True},{"duplicate":True},{"missing":True},
])
def test_invalid_metadata_rejected(monkeypatch,kwargs):
    patch(monkeypatch,fixture(**kwargs))
    with pytest.raises(RangeFetchError):
        probe.inspect_remote_projected_grid(URL,approved=True)

def test_changed_object_size_rejected(monkeypatch):
    patch(monkeypatch,fixture(),changed_size=True)
    with pytest.raises(RangeFetchError,match="changed"):
        probe.inspect_remote_projected_grid(URL,approved=True)

def test_truncated_range_rejected(monkeypatch):
    patch(monkeypatch,fixture(),truncated=True)
    with pytest.raises((RangeFetchError,struct.error)):
        probe.inspect_remote_projected_grid(URL,approved=True)
