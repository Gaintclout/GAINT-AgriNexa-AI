"""Explicitly approved, checksum-pinned GeoTIFF staging; no automatic authorization."""
import hashlib
import os
import re
import tempfile
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, build_opener
from .scim_asset_url_policy import validate_asset_url
from .scim_discovery import NoRedirects

MAX_ASSET_BYTES = 50 * 1024 * 1024
CHUNK_BYTES = 64 * 1024
SHA256_PATTERN = re.compile(r"^[a-fA-F0-9]{64}$")
TIFF_MAGIC = (b"II*\x00", b"MM\x00*", b"II+\x00", b"MM\x00+")

class AssetStagingError(Exception):
    pass

def stage_verified_geotiff(url: str, expected_sha256: str, destination: Path, *,
                           approved: bool = False, opener=None) -> dict:
    """Stage only with explicit approval and an independently supplied SHA-256.

    Caller must verify scene provenance and approval outside this function.
    Never stage to an existing path. A checksum match is not raster safety validation.
    """
    if not approved:
        raise AssetStagingError("Explicit asset download approval required")
    validate_asset_url(url)
    if not isinstance(expected_sha256, str) or not SHA256_PATTERN.fullmatch(expected_sha256):
        raise ValueError("A valid expected SHA-256 is required")
    destination = Path(destination)
    if destination.suffix.lower() not in (".tif", ".tiff") or destination.is_symlink():
        raise ValueError("Destination must be a non-symlink TIFF path")
    if destination.exists():
        raise FileExistsError("Destination already exists")
    if not destination.parent.is_dir() or destination.parent.is_symlink():
        raise ValueError("Destination parent must be an existing real directory")
    client = opener if opener is not None else build_opener(NoRedirects())
    request = Request(url, headers={"User-Agent": "GAINT-AgriNexa-SCIM/0.1", "Accept-Encoding": "identity"})
    temp_path = None
    digest = hashlib.sha256()
    size = 0
    header = b""
    try:
        with client.open(request, timeout=20) as response:
            if response.status != 200 or response.geturl() != url:
                raise AssetStagingError("Unexpected asset response or redirect")
            length = response.headers.get("Content-Length")
            if length is not None:
                try:
                    declared = int(length)
                except ValueError as exc:
                    raise AssetStagingError("Invalid content length") from exc
                if declared < 0 or declared > MAX_ASSET_BYTES:
                    raise AssetStagingError("Asset exceeds staging size limit")
            with tempfile.NamedTemporaryFile(dir=destination.parent, prefix=".scim-", suffix=".part",
                                             delete=False) as temp:
                temp_path = Path(temp.name)
                while True:
                    chunk = response.read(CHUNK_BYTES)
                    if not chunk:
                        break
                    size += len(chunk)
                    if size > MAX_ASSET_BYTES:
                        raise AssetStagingError("Asset exceeds staging size limit")
                    if len(header) < 4:
                        header = (header + chunk)[:4]
                    digest.update(chunk)
                    temp.write(chunk)
                temp.flush()
                os.fsync(temp.fileno())
        if size < 8 or header not in TIFF_MAGIC:
            raise AssetStagingError("Not a TIFF file")
        if digest.hexdigest() != expected_sha256.lower():
            raise AssetStagingError("SHA-256 mismatch")
        # Exclusive creation prevents accidental replacement of existing staged imagery.
        with open(destination, "xb") as target, open(temp_path, "rb") as source:
            while True:
                chunk = source.read(CHUNK_BYTES)
                if not chunk:
                    break
                target.write(chunk)
            target.flush()
            os.fsync(target.fileno())
        return {"bytes": size, "sha256": digest.hexdigest(), "checksum_verified": True,
                "raster_structure_verified": False, "provenance_verified": False}
    except (HTTPError, URLError, TimeoutError, OSError) as exc:
        raise AssetStagingError("Asset staging failed") from exc
    finally:
        if temp_path is not None:
            temp_path.unlink(missing_ok=True)
