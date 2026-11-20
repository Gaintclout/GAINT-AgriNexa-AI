"""Offline, bounded parcel-window extraction from trusted local GeoTIFFs.

The input must already be staged and approved by the caller. This function
does not establish satellite provenance or independently verify input checksums.
"""
from hashlib import sha256
from pathlib import Path
import os
import tempfile
import rasterio
from rasterio.windows import Window, transform as window_transform
from .scim_cog_window_plan import plan_parcel_window
from .scim_rasterio_pipeline import _trusted_path

def extract_local_parcel_window(root: Path, filename: str, parcel_geometry: dict,
                                destination: Path, *, margin_pixels: int = 1) -> dict:
    """Create a new georeferenced uint16 crop; never overwrite existing output."""
    plan = plan_parcel_window(root, filename, parcel_geometry, margin_pixels=margin_pixels)
    source_path = _trusted_path(root, filename)
    destination = Path(destination)
    if destination.suffix.lower() not in (".tif", ".tiff"):
        raise ValueError("Destination must be a GeoTIFF")
    if destination.is_symlink() or destination.exists():
        raise FileExistsError("Destination already exists or is a symlink")
    if not destination.parent.is_dir() or destination.parent.is_symlink():
        raise ValueError("Destination directory must be an existing real directory")
    temporary = None
    created = False
    try:
        with rasterio.open(source_path, "r", sharing=False) as source:
            window = Window(plan["col_off"], plan["row_off"], plan["width"], plan["height"])
            values = source.read(1, window=window, boundless=False)
            if values.shape != (plan["height"], plan["width"]) or values.dtype.name != "uint16":
                raise ValueError("Unexpected raster window shape or type")
            profile = source.profile.copy()
            profile.update(driver="GTiff", width=plan["width"], height=plan["height"],
                           count=1, dtype="uint16", transform=window_transform(window, source.transform))
            profile.pop("blockxsize", None)
            profile.pop("blockysize", None)
            profile.pop("tiled", None)
            with tempfile.NamedTemporaryFile(dir=destination.parent, prefix=".scim-crop-",
                                             suffix=".tif", delete=False) as temp:
                temporary = Path(temp.name)
            with rasterio.open(temporary, "w", **profile) as target:
                target.write(values, 1)
        digest = sha256()
        with temporary.open("rb") as stream:
            while chunk := stream.read(65536):
                digest.update(chunk)
        with destination.open("xb") as target, temporary.open("rb") as source:
            created = True
            while chunk := source.read(65536):
                target.write(chunk)
            target.flush()
            os.fsync(target.fileno())
        return {"filename": destination.name, "sha256": digest.hexdigest(),
                "bytes": destination.stat().st_size, "window": plan,
                "output_georeferenced": True, "source_checksum_verified": False,
                "provenance_verified": False, "network_access": False}
    except Exception:
        if created:
            destination.unlink(missing_ok=True)
        raise
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)
