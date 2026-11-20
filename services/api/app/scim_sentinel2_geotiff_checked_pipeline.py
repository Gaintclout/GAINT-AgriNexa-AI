"""Offline Sentinel-2 pipeline with GeoTIFF-probe-consistent raster grids.

Each decoded asset must provide metadata probed under the same pinned object
version by the caller. The checks establish internal consistency, not
authenticity, cryptographic integrity, or real-world source provenance.
"""
from .scim_cog_range_fetch import RangeFetchError
from .scim_cog_verified_geotiff_grid import assemble_verified_geotiff_grid
from .scim_sentinel2_scene_bundle import REQUIRED,analyze_sentinel2_scene_bundle

def analyze_geotiff_checked_sentinel2_scene(parcel,scene,decoded_assets,calibration):
    if not isinstance(scene,dict) or not isinstance(scene.get("id"),str):
        raise RangeFetchError("Scene identifier required")
    if not isinstance(decoded_assets,dict) or set(decoded_assets)!=set(REQUIRED):
        raise RangeFetchError("Exactly five GeoTIFF-checked Sentinel-2 assets required")
    assets={}
    for band in REQUIRED:
        item=decoded_assets[band]
        if not isinstance(item,dict) or item.get("scene_id")!=scene["id"] or item.get("band")!=band:
            raise RangeFetchError("Decoded GeoTIFF scene or band mismatch")
        for key in ("decoded","raster","tile_table","georef"):
            if not isinstance(item.get(key),dict):
                raise RangeFetchError("Complete GeoTIFF probe results required")
        grid=assemble_verified_geotiff_grid(
            item["decoded"],item["tile_table"],item["georef"],item["raster"])
        assets[band]={"scene_id":scene["id"],"band":band,
                      "decoded":True,"version_pinned":True,
                      "grid":{key:grid[key] for key in
                              ("width","height","crs","transform","values")}}
    result=analyze_sentinel2_scene_bundle(
        parcel,{"scene":scene,"assets":assets,"calibration":calibration})
    return {**result,"geotiff_probe_checked_assets":5,
            "georeferencing_consistency_checked":True,
            "raster_georeferencing_authenticated":False,
            "scene_identity_authenticated":False,
            "source_checksum_verified":False,"provenance_verified":False}
