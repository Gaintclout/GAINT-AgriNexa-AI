"""Fail-closed offline Sentinel-2 scene bundle validation and analysis.

Scene identity and asset metadata are supplied by the caller and are NOT
authenticated against STAC or satellite provider records. This boundary
requires matching declared scene identifiers, bounded grids and explicit
calibration values before invoking existing parcel analysis. No downloads.
"""
from datetime import datetime
from math import isfinite
from .scim_cog_range_fetch import RangeFetchError
from .scim_sentinel2_parcel_analysis import analyze_sentinel2_parcel

REQUIRED=("B04","B08","B03","B11","SCL")
BAND_NAMES={"B04":"red","B08":"nir","B03":"green","B11":"swir1"}

def analyze_sentinel2_scene_bundle(parcel,bundle):
    if not isinstance(bundle,dict):
        raise RangeFetchError("Invalid Sentinel-2 scene bundle")
    scene=bundle.get("scene")
    if not isinstance(scene,dict) or scene.get("collection")!="sentinel-2-l2a":
        raise RangeFetchError("Sentinel-2 L2A scene metadata required")
    scene_id=scene.get("id")
    if not isinstance(scene_id,str) or not 1<=len(scene_id)<=200:
        raise RangeFetchError("Invalid scene identifier")
    captured=scene.get("captured_at")
    try:
        stamp=datetime.fromisoformat(captured.replace("Z","+00:00"))
        if stamp.tzinfo is None or stamp.utcoffset() is None:
            raise ValueError("Timezone required")
    except (AttributeError,TypeError,ValueError) as exc:
        raise RangeFetchError("Invalid scene acquisition timestamp") from exc
    assets=bundle.get("assets")
    if not isinstance(assets,dict) or set(assets)!=set(REQUIRED):
        raise RangeFetchError("Exactly five Sentinel-2 assets required")
    grids={}
    for band in REQUIRED:
        asset=assets[band]
        if not isinstance(asset,dict) or asset.get("scene_id")!=scene_id:
            raise RangeFetchError("Scene asset identity mismatch")
        if asset.get("band")!=band:
            raise RangeFetchError("Scene asset band mismatch")
        if asset.get("decoded") is not True or asset.get("version_pinned") is not True:
            raise RangeFetchError("Pinned decoded scene assets required")
        grid=asset.get("grid")
        if not isinstance(grid,dict):
            raise RangeFetchError("Missing decoded asset grid")
        grids[band]=grid
    calibration=bundle.get("calibration")
    if not isinstance(calibration,dict):
        raise RangeFetchError("Scene calibration metadata required")
    quant=calibration.get("quantification")
    offsets=calibration.get("offsets")
    if (type(quant) not in (int,float) or not isfinite(quant) or quant<=0 or
            not isinstance(offsets,dict) or set(offsets)!=set(REQUIRED)-{"SCL"} or
            any(type(v) not in (int,float) or not isfinite(v) for v in offsets.values())):
        raise RangeFetchError("Invalid Sentinel-2 calibration metadata")
    result=analyze_sentinel2_parcel(
        parcel,{name:grids[band] for band,name in BAND_NAMES.items()},
        grids["SCL"],quantification=quant,offsets=offsets)
    return {**result,"scene_id":scene_id,"captured_at":stamp.isoformat(),
            "scene_assets_checked":len(REQUIRED),
            "scene_identity_consistent":True,
            "scene_identity_authenticated":False,
            "calibration_metadata_verified":False,
            "source_checksum_verified":False,"provenance_verified":False}
