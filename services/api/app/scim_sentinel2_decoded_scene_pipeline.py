"""Offline five-asset decoded TIFF adapter for Sentinel-2 parcel analysis.

Consumes caller-supplied pinned decoder outputs and bounded raster metadata.
This does not fetch imagery or authenticate scene identity/georeferencing.
"""
from .scim_cog_range_fetch import RangeFetchError
from .scim_cog_decoded_grid_assembly import assemble_decoded_tile_grid
from .scim_sentinel2_scene_bundle import REQUIRED,analyze_sentinel2_scene_bundle

def analyze_decoded_sentinel2_scene(parcel,scene,decoded_assets,calibration):
    if not isinstance(scene,dict) or not isinstance(scene.get("id"),str):
        raise RangeFetchError("Scene identifier required")
    if not isinstance(decoded_assets,dict) or set(decoded_assets)!=set(REQUIRED):
        raise RangeFetchError("Exactly five decoded Sentinel-2 assets required")
    assets={}
    for band in REQUIRED:
        item=decoded_assets[band]
        if not isinstance(item,dict) or item.get("scene_id")!=scene["id"]:
            raise RangeFetchError("Decoded asset scene mismatch")
        if item.get("band")!=band:
            raise RangeFetchError("Decoded asset band mismatch")
        metadata=item.get("raster")
        decoded=item.get("decoded")
        if not isinstance(metadata,dict) or not isinstance(decoded,dict):
            raise RangeFetchError("Raster metadata and decoded pixels required")
        required={"width","height","tile_width","tile_height","crs","transform"}
        if set(metadata)!=required:
            raise RangeFetchError("Incomplete raster metadata")
        grid=assemble_decoded_tile_grid(decoded,**metadata)
        assets[band]={"scene_id":scene["id"],"band":band,
                      "decoded":grid["decoded"],
                      "version_pinned":grid["version_pinned"],
                      "grid":{k:grid[k] for k in
                              ("width","height","crs","transform","values")}}
    result=analyze_sentinel2_scene_bundle(
        parcel,{"scene":scene,"assets":assets,"calibration":calibration})
    return {**result,"decoded_tile_grids_assembled":5,
            "raster_georeferencing_authenticated":False,
            "scene_identity_authenticated":False,
            "source_checksum_verified":False,"provenance_verified":False}
