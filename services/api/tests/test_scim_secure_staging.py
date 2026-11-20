import hashlib
import pytest
from app.scim_secure_staging import stage_verified_geotiff, AssetStagingError

URL = "https://sentinel-cogs.s3.us-west-2.amazonaws.com/example/B04.tif"
DATA = b"II*\x00" + b"abcd" * 4

class Response:
    status = 200
    headers = {}
    def __init__(self, data=DATA):
        self.data = data
        self.offset = 0
    def __enter__(self):
        return self
    def __exit__(self, *args):
        pass
    def geturl(self):
        return URL
    def read(self, size):
        chunk = self.data[self.offset:self.offset + size]
        self.offset += len(chunk)
        return chunk

class Opener:
    def __init__(self, data=DATA):
        self.data = data
    def open(self, request, timeout):
        assert request.full_url == URL
        assert timeout == 20
        return Response(self.data)

def test_approval_required(tmp_path):
    with pytest.raises(AssetStagingError, match="approval"):
        stage_verified_geotiff(URL, hashlib.sha256(DATA).hexdigest(), tmp_path / "a.tif", opener=Opener())

def test_stages_only_matching_checksum(tmp_path):
    target = tmp_path / "a.tif"
    report = stage_verified_geotiff(URL, hashlib.sha256(DATA).hexdigest(), target,
                                    approved=True, opener=Opener())
    assert target.read_bytes() == DATA
    assert report["checksum_verified"]
    assert not report["raster_structure_verified"]
    assert not report["provenance_verified"]

def test_checksum_mismatch_leaves_no_file(tmp_path):
    target = tmp_path / "a.tif"
    with pytest.raises(AssetStagingError, match="SHA-256"):
        stage_verified_geotiff(URL, "0" * 64, target, approved=True, opener=Opener())
    assert not target.exists()
    assert not list(tmp_path.glob(".scim-*"))

def test_rejects_non_tiff(tmp_path):
    target = tmp_path / "a.tif"
    data = b"not-a-tiff"
    with pytest.raises(AssetStagingError, match="TIFF"):
        stage_verified_geotiff(URL, hashlib.sha256(data).hexdigest(), target,
                               approved=True, opener=Opener(data))
    assert not target.exists()

def test_rejects_existing_destination(tmp_path):
    target = tmp_path / "a.tif"
    target.write_bytes(b"existing")
    with pytest.raises(FileExistsError):
        stage_verified_geotiff(URL, hashlib.sha256(DATA).hexdigest(), target,
                               approved=True, opener=Opener())
    assert target.read_bytes() == b"existing"

def test_rejects_untrusted_url(tmp_path):
    with pytest.raises(ValueError):
        stage_verified_geotiff("http://127.0.0.1/a.tif", "0" * 64,
                               tmp_path / "a.tif", approved=True, opener=Opener())
