"""No-network tests for checksum-verified asset staging."""
from hashlib import sha256
from io import BytesIO
import pytest
from app import scim_asset_staging as staging

URL = "https://sentinel-cogs.s3.us-west-2.amazonaws.com/example.tif"

class FakeResponse(BytesIO):
    status = 200
    headers = {"Content-Length": "8"}

class FakeOpener:
    def __init__(self, payload):
        self.payload = payload
    def open(self, request, timeout):
        return FakeResponse(self.payload)

def test_staging_requires_matching_checksum(tmp_path, monkeypatch):
    data = b"II*\x00DATA"
    monkeypatch.setattr(staging, "build_opener", lambda *_: FakeOpener(data))
    target = staging.stage_verified_geotiff(URL, sha256(data).hexdigest(), tmp_path, "scene.tif")
    assert target.read_bytes() == data

def test_staging_rejects_bad_digest_and_cleans_temp(tmp_path, monkeypatch):
    data = b"II*\x00DATA"
    monkeypatch.setattr(staging, "build_opener", lambda *_: FakeOpener(data))
    with pytest.raises(ValueError, match="checksum"):
        staging.stage_verified_geotiff(URL, "0" * 64, tmp_path, "scene.tif")
    assert list(tmp_path.iterdir()) == []

def test_staging_rejects_untrusted_host(tmp_path):
    with pytest.raises(ValueError):
        staging.stage_verified_geotiff("https://localhost/scene.tif", "0" * 64, tmp_path, "scene.tif")

def test_staging_rejects_destination_traversal(tmp_path):
    with pytest.raises(ValueError, match="destination"):
        staging.stage_verified_geotiff(URL, "0" * 64, tmp_path, "../scene.tif")
