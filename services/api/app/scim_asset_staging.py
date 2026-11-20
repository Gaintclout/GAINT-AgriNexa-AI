"""Bounded HTTPS staging for explicitly approved SCIM GeoTIFF assets.

No redirects, no arbitrary URLs, no asset execution, and no implicit STAC trust.
The caller must supply a preverified SHA-256 digest and a trusted staging root.
"""
from hashlib import sha256
from pathlib import Path
from tempfile import NamedTemporaryFile
from urllib.request import Request, build_opener, HTTPRedirectHandler
from urllib.error import HTTPError, URLError
import os
import re
from .scim_asset_url_policy import validate_asset_url

MAX_DOWNLOAD_BYTES = 50_000_000

class _NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise ValueError("Satellite asset redirects are forbidden")

def stage_verified_geotiff(url: str, expected_sha256: str, root: Path,
                           destination: str) -> Path:
    validate_asset_url(url)
    if not re.fullmatch(r"[0-9a-fA-F]{64}", expected_sha256):
        raise ValueError("Verified SHA-256 checksum required")
    if (not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,127}\.tiff?", destination)
            or destination.startswith(".")):
        raise ValueError("Unsafe destination filename")
    base = Path(root).resolve(strict=True)
    if not base.is_dir():
        raise ValueError("Staging root must be a directory")
    target = base / destination
    if target.exists() or target.is_symlink():
        raise ValueError("Destination already exists")
    request = Request(url, headers={"User-Agent": "GAINT-AgriNexa-SCIM/1.0", "Accept": "image/tiff,application/octet-stream"})
    opener = build_opener(_NoRedirect())
    temporary = None
    try:
        with opener.open(request, timeout=15) as response:
            if response.status != 200:
                raise ValueError("Unexpected asset response status")
            declared = response.headers.get("Content-Length")
            if declared is not None and (not declared.isdecimal() or int(declared) > MAX_DOWNLOAD_BYTES):
                raise ValueError("Asset exceeds download limit")
            digest = sha256()
            total = 0
            with NamedTemporaryFile(dir=base, prefix=".scim-", suffix=".part", delete=False) as handle:
                temporary = Path(handle.name)
                while True:
                    block = response.read(min(1024 * 1024, MAX_DOWNLOAD_BYTES - total + 1))
                    if not block:
                        break
                    total += len(block)
                    if total > MAX_DOWNLOAD_BYTES:
                        raise ValueError("Asset exceeds download limit")
                    digest.update(block)
                    handle.write(block)
        if total == 0 or digest.hexdigest() != expected_sha256.lower():
            raise ValueError("Asset checksum mismatch")
        with temporary.open("rb") as handle:
            if handle.read(4) not in (b"II*\x00", b"MM\x00*"):
                raise ValueError("Asset is not a classic GeoTIFF")
        os.link(temporary, target)
        return target
    except (HTTPError, URLError) as exc:
        raise ValueError("Trusted satellite asset unavailable") from exc
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)
