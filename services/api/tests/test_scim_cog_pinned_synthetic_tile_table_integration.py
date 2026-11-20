"""Real classic-TIFF IFD and tile-table readers with offline pinned HTTP ranges.

Builds a bounded synthetic tiled TIFF in memory. No live imagery or network.
"""
import io
import re
import struct
import pytest

from app.scim_cog_ifd_probe import inspect_remote_classic_ifd
from app.scim_cog_tile_table import inspect_remote_tile_table
from app.scim_cog_pinned_metadata_opener import PinnedMetadataOpener
from app.scim_cog_range_fetch import RangeFetchError

URL="https://sentinel-cogs.s3.us-west-2.amazonaws.com/synthetic-tiled.tif"
ETAG='"synthetic-tiled-v1"'

def make_tiff():
    data=bytearray(256)
    data[:8]=b"II"+struct.pack("<HI",42,16)
    tags=[
        (256,4,1,512),
        (257,4,1,256),
        (322,4,1,256),
        (323,4,1,256),
        (324,4,2,128),
        (325,4,2,136),
    ]
    struct.pack_into("<H",data,16,len(tags))
    for i,tag in enumerate(tags):
        struct.pack_into("<HHII",data,18+i*12,*tag)
    struct.pack_into("<I",data,18+len(tags)*12,0)
    struct.pack_into("<II",data,128,160,164)
    struct.pack_into("<II",data,136,4,4)
    data[160:168]=b"abcdefgh"
    return bytes(data)

class Response:
    status=206
    def __init__(self,url,data,start,end,etag):
        self.url=url
        self.body=io.BytesIO(data[start:end+1])
        self.headers={"ETag":etag,"Content-Range":f"bytes {start}-{end}/{len(data)}",
                      "Content-Length":str(end-start+1)}
    def geturl(self):
        return self.url
    def read(self,n=-1):
        return self.body.read(n)
    def close(self):
        self.body.close()
    def __enter__(self):
        return self
    def __exit__(self,*args):
        self.close()

class Opener:
    def __init__(self,data,*,etag=ETAG):
        self.data=data
        self.etag=etag
        self.requests=[]
    def open(self,request,timeout=15):
        self.requests.append(request)
        match=re.fullmatch(r"bytes=(\d+)-(\d+)",request.get_header("Range",""))
        assert match is not None
        start,end=map(int,match.groups())
        assert 0<=start<=end<len(self.data)
        return Response(request.full_url,self.data,start,end,self.etag)

def test_real_ifd_parser_with_pinned_metadata():
    transport=Opener(make_tiff())
    pinned=PinnedMetadataOpener(transport,ETAG)
    result=inspect_remote_classic_ifd(URL,approved=True,opener=pinned)
    assert (result["width"],result["height"])==(512,256)
    assert (result["tile_width"],result["tile_height"])==(256,256)
    assert result["tile_arrays"]["tile_offsets"]["count"]==2
    assert pinned.requests==len(transport.requests)
    assert pinned.requests>=3
    assert all(req.get_header("If-match")==ETAG for req in transport.requests)

def test_real_tile_table_parser_with_pinned_metadata():
    transport=Opener(make_tiff())
    pinned=PinnedMetadataOpener(transport,ETAG)
    table=inspect_remote_tile_table(URL,approved=True,opener=pinned)
    assert table["tile_columns"]==2
    assert table["tile_rows"]==1
    assert [t["offset"] for t in table["tiles"]]==[160,164]
    assert [t["byte_count"] for t in table["tiles"]]==[4,4]
    assert table["object_bytes"]==256
    assert pinned.requests==len(transport.requests)
    assert all(req.get_header("If-match")==ETAG for req in transport.requests)
    assert table["source_checksum_verified"] is False

def test_real_tile_table_rejects_changed_etag():
    pinned=PinnedMetadataOpener(Opener(make_tiff(),etag='"different"'),ETAG)
    with pytest.raises(RangeFetchError):
        inspect_remote_tile_table(URL,approved=True,opener=pinned)
    assert pinned.requests==0

def test_real_tile_table_requires_approval():
    transport=Opener(make_tiff())
    pinned=PinnedMetadataOpener(transport,ETAG)
    with pytest.raises(RangeFetchError,match="approval"):
        inspect_remote_tile_table(URL,approved=False,opener=pinned)
    assert transport.requests==[]
