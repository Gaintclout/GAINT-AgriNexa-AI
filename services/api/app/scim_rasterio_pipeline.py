"""Offline SCIM raster decoding, alignment and parcel masking.

Only administrator-staged local GeoTIFFs under a configured trusted directory
are accepted. Network/VSI paths, symlinks, and untrusted URLs are rejected.
This module never downloads STAC assets or trusts a user-supplied parcel mask.
"""
from pathlib import Path
import numpy as np
import rasterio
from rasterio import open as raster_open
from rasterio.enums import Resampling
from rasterio.features import geometry_mask
from rasterio.warp import reproject, transform_geom
from shapely.geometry import shape, mapping
from shapely.validation import explain_validity
from .scim_bands import BAND_MAP
from .scim_contracts import SatelliteProvider
from .scim_raster_grid import RasterGrid, RasterEvaluationRequest, evaluate_raster_grid

MAX_PIXELS = 10000
MAX_FILE_BYTES = 100_000_000

def _trusted_path(root: Path, filename: str) -> Path:
    if (not filename or Path(filename).is_absolute() or "\\" in filename or ":" in filename
            or filename.startswith("/") or any(ord(ch) < 33 or ord(ch) == 127 for ch in filename)):
        raise ValueError("Only relative local raster paths are permitted")
    base = Path(root).resolve(strict=True)
    candidate = base / filename
    if any(part in (".", "..") for part in Path(filename).parts):
        raise ValueError("Unsafe raster path")
    if any(part.is_symlink() for part in (base / filename).parents if part != base) or candidate.is_symlink():
        raise ValueError("Symlinked raster paths are forbidden")
    resolved = candidate.resolve(strict=True)
    if not resolved.is_relative_to(base) or not resolved.is_file() or resolved.suffix.lower() not in (".tif", ".tiff"):
        raise ValueError("Raster must be a trusted local GeoTIFF")
    if resolved.stat().st_size > MAX_FILE_BYTES:
        raise ValueError("Raster exceeds file size limit")
    return resolved

def _read_band(root, filename, reference=None, *, categorical=False):
    path = _trusted_path(root, filename)
    with raster_open(path, "r", sharing=False) as source:
        if source.driver != "GTiff" or source.count != 1 or source.crs is None:
            raise ValueError("Single-band georeferenced GeoTIFF required")
        if source.dtypes[0] != "uint16":
            raise ValueError("Source raster must contain uint16 digital numbers")
        if source.width * source.height > MAX_PIXELS * 16:
            raise ValueError("Source raster exceeds processing pixel limit")
        if reference is None:
            if source.width * source.height > MAX_PIXELS:
                raise ValueError("Reference raster exceeds processing pixel limit")
            if not source.transform.is_rectilinear or source.transform.a <= 0 or source.transform.e >= 0:
                raise ValueError("Unsupported reference raster transform")
            array = source.read(1)
            return array, (source.crs, source.transform, source.width, source.height)
        crs, transform, width, height = reference
        array = np.zeros((height, width), dtype=np.uint16)
        reproject(source=rasterio_band(source), destination=array,
                  src_transform=source.transform, src_crs=source.crs,
                  src_nodata=source.nodata, dst_transform=transform, dst_crs=crs,
                  dst_nodata=0, resampling=Resampling.nearest if categorical else Resampling.bilinear)
        return array, reference

def rasterio_band(source):
    return rasterio.band(source, 1)

def evaluate_staged_scene(root: Path, provider: SatelliteProvider, qa_filename: str,
                          band_files: dict[str, str], parcel_geometry: dict,
                          *, sentinel_quantification=None, sentinel_offsets=None):
    """Evaluate one bounded grid against a verified WGS84 GeoJSON polygon."""
    provider = SatelliteProvider(provider)
    if set(band_files) != set(BAND_MAP[provider].values()):
        raise ValueError("Exact provider band mapping required")
    polygon = shape(parcel_geometry)
    if polygon.geom_type not in ("Polygon", "MultiPolygon") or polygon.is_empty or not polygon.is_valid:
        raise ValueError("Invalid parcel polygon: " + explain_validity(polygon))
    if not (-180 <= polygon.bounds[0] < polygon.bounds[2] <= 180 and
            -90 <= polygon.bounds[1] < polygon.bounds[3] <= 90):
        raise ValueError("Parcel must be WGS84 longitude/latitude")
    qa, reference = _read_band(root, qa_filename)
    crs, transform, width, height = reference
    if qa.dtype.kind not in ("u", "i") or qa.min() < 0 or qa.max() > 65535:
        raise ValueError("QA must be uint16")
    projected = transform_geom("EPSG:4326", crs, mapping(polygon))
    mask = geometry_mask([projected], out_shape=(height, width), transform=transform, invert=True)
    if not mask.any():
        raise ValueError("Parcel does not intersect raster")
    def grid(array):
        if array.dtype.kind not in ("u", "i") or array.min() < 0 or array.max() > 65535:
            raise ValueError("Raster values must be uint16")
        return RasterGrid(width=width, height=height, crs=str(crs),
                          transform=tuple(transform)[:6],
                          values=array.astype(np.uint16).ravel().tolist())
    bands = {}
    for band, filename in band_files.items():
        array, _ = _read_band(root, filename, reference, categorical=False)
        bands[band] = grid(array)
    return evaluate_raster_grid(RasterEvaluationRequest(
        provider=provider, qa=grid(qa), bands=bands,
        parcel_mask=mask.ravel().tolist(),
        sentinel_quantification=sentinel_quantification,
        sentinel_offsets=sentinel_offsets))
