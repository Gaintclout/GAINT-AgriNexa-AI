"""Offline TIFF decoding tag inspection tests with exact byte-range responses."""
import io
import struct
import pytest
from app.scim_cog_decode_tags_probe import inspect_remote_decode_tags
from app.scim_cog_pinned_metadata_opener import PinnedMetadataOpener
from app.scim_cog_range_fetch import RangeFetchError

URL="https://sentinel-cogs.s3.us-west-2.amazonaws.com/metadata.tif"
ETAG='"decode-tags-v1"'

def fixture(*,compression=8,bits=16,predictor=1,duplicate=False):
    data=bytearray(256)
    data[:8]=b"II"+struct.pack("<HI",42,16)
    entries=[(258,3,1,bits),(259,3,1,compression),
             (277,3,1,1),(317,3,1,predictor),(339,3,1,1)]
    if duplicate:
        entries.append(entries[1])
    struct.pack_into("<H",data,16,len(entries))
    for i,(tag,kind,count,value) in enumerate(entries):
        struct.pack_into("<HHIH",data,18+12*i,tag,kind,count,value)
    struct.pack_into("<I",data,18+12*len(entries),0)
    return bytes(data)

class Response:
    status=206
    def __init__(self,request,data,start,end,etag):
        self.url=request.full_url
        self.body=io.BytesIO(data[start:end+1])
        self.headers={"ETag":etag,"Content-Range":f"bytes {start}-{end}/{len(data)}",
                      "Content-Length":str(end-start+1)}
    def geturl(self):
        return self.url
    def read(self,size=-1):
        return self.body.read(size)
    def close(self):
        self.body.close()
    def __enter__(self):
        return self
    def __exit__(self,*args):
        self.close()

class Opener:
    def __init__(self,data,etag=ETAG):
        self.data=data
        self.etag=etag
        self.calls=[]
    def open(self,request,timeout=15):
        self.calls.append(request)
        assert request.get_header("If-match")==ETAG
        range_value=request.get_header("Range")
        assert range_value.startswith("bytes=")
        start,end=map(int,range_value[6:].split("-"))
        assert 0<=start<=end<len(self.data)
        return Response(request,self.data,start,end,self.etag)

def test_reads_pinned_deflate_uint16_tags():
    transport=Opener(fixture())
    result=inspect_remote_decode_tags(URL,approved=True,
        opener=PinnedMetadataOpener(transport,ETAG))
    assert result["compression"]==8
    assert result["bits_per_sample"]==16
    assert result["samples_per_pixel"]==1
    assert result["decode_tags_validated"] is True
    assert len(transport.calls)==3

@pytest.mark.parametrize("kwargs",[
    {"compression":5},{"bits":32},{"predictor":2},{"duplicate":True}])
def test_unsupported_or_duplicate_tags_rejected(kwargs):
    transport=Opener(fixture(**kwargs))
    with pytest.raises(RangeFetchError):
        inspect_remote_decode_tags(URL,approved=True,
            opener=PinnedMetadataOpener(transport,ETAG))

def test_etag_change_rejected():
    transport=Opener(fixture(),etag='"changed"')
    with pytest.raises(RangeFetchError):
        inspect_remote_decode_tags(URL,approved=True,
            opener=PinnedMetadataOpener(transport,ETAG))

def test_requires_approval():
    transport=Opener(fixture())
    with pytest.raises(RangeFetchError,match="approval"):
        inspect_remote_decode_tags(URL,opener=PinnedMetadataOpener(transport,ETAG))
    assert transport.calls==[]
