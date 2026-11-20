"""Offline tests for ETag-pinned range sessions."""
import pytest
from app import scim_cog_pinned_session as module
from app.scim_cog_range_fetch import RangeFetchError

URL="https://sentinel-cogs.s3.us-west-2.amazonaws.com/synthetic.tif"
ETAG='"scene-2026-v1"'

def test_session_uses_same_etag_and_size(monkeypatch):
    calls=[]
    def fake(url,start,length,**kwargs):
        calls.append((start,length,kwargs["expected_etag"]))
        return {"data":b"x"*length,"total_bytes":4096}
    monkeypatch.setattr(module,"fetch_pinned_cog_range",fake)
    session=module.PinnedRangeSession(ETAG)
    assert session.fetch(URL,0,4,approved=True)["data"]==b"xxxx"
    assert session.fetch(URL,100,8,approved=True)["data"]==b"x"*8
    assert calls==[(0,4,ETAG),(100,8,ETAG)]
    assert session.expected_object_bytes==4096
    assert session.requests==2

def test_session_requires_approval(monkeypatch):
    monkeypatch.setattr(module,"fetch_pinned_cog_range",
                        lambda *a,**k:pytest.fail("unexpected fetch"))
    with pytest.raises(RangeFetchError,match="approval"):
        module.PinnedRangeSession(ETAG).fetch(URL,0,4)

def test_size_change_rejected(monkeypatch):
    totals=iter([4096,4097])
    monkeypatch.setattr(module,"fetch_pinned_cog_range",
                        lambda *a,**k:{"data":b"abcd","total_bytes":next(totals)})
    session=module.PinnedRangeSession(ETAG)
    session.fetch(URL,0,4,approved=True)
    with pytest.raises(RangeFetchError,match="size changed"):
        session.fetch(URL,100,4,approved=True)
    assert session.requests==1

@pytest.mark.parametrize("etag",["bad",'W/"weak"',""])
def test_weak_or_invalid_etag_rejected(etag):
    with pytest.raises(RangeFetchError):
        module.PinnedRangeSession(etag)

def test_opener_override_rejected(monkeypatch):
    monkeypatch.setattr(module,"fetch_pinned_cog_range",
                        lambda *a,**k:pytest.fail("unexpected fetch"))
    session=module.PinnedRangeSession(ETAG,opener=object())
    with pytest.raises(RangeFetchError,match="override"):
        session.fetch(URL,0,4,approved=True,opener=object())
