"""Private, content-addressed storage for field evidence photographs."""

import hashlib
import os
import tempfile
from pathlib import Path

from fastapi import HTTPException

MAX_PHOTO_BYTES = 8 * 1024 * 1024

SUPPORTED_IMAGES = {
    "image/jpeg": (b"\xff\xd8\xff", ".jpg"),
    "image/png": (b"\x89PNG\r\n\x1a\n", ".png"),
    "image/webp": (b"RIFF", ".webp"),
}


def storage_root() -> Path:
    configured = os.environ.get("AGRINEXA_PRIVATE_PHOTO_DIR", "")
    if not configured:
        raise HTTPException(
            status_code=503,
            detail="Private photo storage is not configured",
        )
    root = Path(configured).expanduser().resolve()
    if not root.is_dir():
        raise HTTPException(
            status_code=503,
            detail="Private photo storage directory does not exist",
        )
    return root


def validate_photo(data: bytes, content_type: str) -> str:
    if not data:
        raise HTTPException(422, "Photo is empty")

    if len(data) > MAX_PHOTO_BYTES:
        raise HTTPException(413, "Photo exceeds 8 MB")

    if content_type not in SUPPORTED_IMAGES:
        raise HTTPException(415, "Unsupported image format")

    signature, extension = SUPPORTED_IMAGES[content_type]

    if not data.startswith(signature):
        raise HTTPException(422, "Image signature does not match content type")

    if content_type == "image/webp" and data[8:12] != b"WEBP":
        raise HTTPException(422, "Invalid WebP signature")

    # Validate that the complete image can be decoded, not only its header.
    try:
        from PIL import Image, UnidentifiedImageError
        from io import BytesIO

        with Image.open(BytesIO(data)) as image:
            if image.format not in {"JPEG", "PNG", "WEBP"}:
                raise ValueError("Unsupported decoded image format")
            expected = {
                "image/jpeg": "JPEG",
                "image/png": "PNG",
                "image/webp": "WEBP",
            }[content_type]
            if image.format != expected:
                raise ValueError("Image content type mismatch")
            image.verify()
    except (ImportError, UnidentifiedImageError, ValueError, OSError) as exc:
        raise HTTPException(
            422,
            "Photo could not be verified",
        ) from exc

    return extension


def save_private_photo(data: bytes, content_type: str):
    extension = validate_photo(data, content_type)
    digest = hashlib.sha256(data).hexdigest()

    root = storage_root()
    directory = root / digest[:2] / digest[2:4]
    directory.mkdir(parents=True, exist_ok=True)

    destination = directory / f"{digest}{extension}"

    if destination.exists():
        if hashlib.sha256(destination.read_bytes()).hexdigest() != digest:
            raise HTTPException(409, "Stored photo integrity conflict")
        return digest, len(data)

    temporary = None

    try:
        with tempfile.NamedTemporaryFile(
            mode="wb",
            dir=directory,
            prefix=".upload-",
            delete=False,
        ) as handle:
            temporary = Path(handle.name)
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())

        # Exclusive creation prevents overwriting existing evidence.
        try:
            os.link(temporary, destination)
        except FileExistsError:
            if hashlib.sha256(destination.read_bytes()).hexdigest() != digest:
                raise HTTPException(409, "Stored photo integrity conflict")
        finally:
            temporary.unlink(missing_ok=True)

    except OSError as exc:
        if temporary is not None:
            temporary.unlink(missing_ok=True)
        raise HTTPException(
            503,
            "Private photo storage is unavailable",
        ) from exc

    return digest, len(data)


def private_photo_path(digest: str, content_type: str) -> Path:
    if len(digest) != 64 or any(character not in "0123456789abcdef" for character in digest):
        raise HTTPException(404, "Evidence photo not found")
    if content_type not in SUPPORTED_IMAGES:
        raise HTTPException(404, "Evidence photo not found")
    path = storage_root() / digest[:2] / digest[2:4] / f"{digest}{SUPPORTED_IMAGES[content_type][1]}"
    if not path.is_file():
        raise HTTPException(404, "Evidence photo not found")
    return path
