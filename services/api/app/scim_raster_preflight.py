"""Offline preflight of checksum-verified scene rasters before parcel evaluation.

No network access or changes to the existing raster evaluation pipeline.
"""
from pathlib import Path
import rasterio
from rasterio.warp import transform_bounds
from shapely.geometry import shape
from .scim_scene_manifest import StagedSceneManifest, verify_staged_manifest
from .scim_rasterio_pipeline import MAX_PIXELS

def preflight_staged_scene(root: Path, manifest: StagedSceneManifest, parcel_geometry: dict) -> dict:
    paths = verify_staged_manifest(root, manifest)
    polygon = shape(parcel_geometry)
    if polygon.geom_type not in ("Polygon", "MultiPolygon") or polygon.is_empty or not polygon.is_valid:
        raise ValueError("Valid WGS84 parcel polygon required")
    west, south, east, north = polygon.bounds
    if not (-180 <= west < east <= 180 and -90 <= south < north <= 90):
        raise ValueError("Parcel coordinates outside WGS84 bounds")
    assets = {}
    for key, filename in paths.items():
        with rasterio.open(filename, "r", sharing=False) as src:
            if src.driver != "GTiff" or src.count != 1 or src.crs is None:
                raise ValueError(f"Invalid single-band georeferenced GeoTIFF: {key}")
            if src.dtypes[0] != "uint16":
                raise ValueError(f"Expected uint16 raster: {key}")
            if src.width <= 0 or src.height <= 0 or src.width * src.height > MAX_PIXELS * 16:
                raise ValueError(f"Raster dimensions exceed processing limits: {key}")
            if not src.transform.is_rectilinear or src.transform.a <= 0 or src.transform.e >= 0:
                raise ValueError(f"Unsupported raster transform: {key}")
            bounds = transform_bounds(src.crs, "EPSG:4326", *src.bounds, densify_pts=21)
            if not all(map(lambda x: isinstance(x, (int, float)) and abs(x) < float("inf"), bounds)):
                raise ValueError(f"Invalid geographic raster bounds: {key}")
            if not (bounds[0] < east and bounds[2] > west and bounds[1] < north and bounds[3] > south):
                raise ValueError(f"Parcel does not intersect raster extent: {key}")
            assets[key] = {"width": src.width, "height": src.height, "crs": str(src.crs),
                           "dtype": src.dtypes[0], "checksum_verified": True}
    qa = assets["qa"]
    if qa["width"] * qa["height"] > MAX_PIXELS:
        raise ValueError("QA reference grid exceeds processing pixel limit")
    return {"scene_id": manifest.scene_id, "provider": manifest.provider.value,
            "assets": assets, "preflight_passed": True, "checksum_verified": True,
            "provenance_verified": False, "parcel_values_evaluated": False}
