"""Offline Sentinel-2 L2A parcel analysis from aligned raw DN and SCL grids.

Uses existing per-band offset calibration and SCL clear-pixel rules.
Resampling is limited to exact 2x nearest-neighbor alignment. Source
georeferencing and calibration metadata are caller-supplied, not verified.
"""
from math import isfinite
from .scim_bands import BAND_MAP
from .scim_contracts import SatelliteProvider
from .scim_calibration import CalibrationInput,calibrate_reflectance
from .scim_cloud_mask import PixelQuality,QualitySensor,is_clear_pixel
from .scim_indices import calculate_indices
from .scim_parcel_band_alignment import align_reflectance_bands
from .scim_parcel_polygon_mask import rasterize_parcel_mask
from .scim_cog_range_fetch import RangeFetchError

MAX_PIXELS=1000000
PROVIDER=SatelliteProvider.sentinel_2
MAPPING=BAND_MAP[PROVIDER]

def analyze_sentinel2_parcel(parcel,raw_bands,scl,*,quantification,offsets):
    if (type(quantification) not in (int,float) or
            not isfinite(quantification) or quantification<=0):
        raise RangeFetchError("Valid Sentinel-2 quantification required")
    if not isinstance(offsets,dict) or not set(MAPPING.values())<=set(offsets):
        raise RangeFetchError("Sentinel-2 per-band offsets required")
    if any(type(offsets[k]) not in (int,float) or not isfinite(offsets[k])
           for k in MAPPING.values()):
        raise RangeFetchError("Invalid Sentinel-2 offsets")
    aligned=align_reflectance_bands(raw_bands)
    bands=aligned["bands"]
    red=bands["red"]
    width,height=red["width"],red["height"]
    if not isinstance(scl,dict):
        raise RangeFetchError("SCL quality grid required")
    scl_alignment=align_reflectance_bands({
        "red":red,"nir":red,"green":red,"swir1":scl})
    quality=scl_alignment["bands"]["swir1"]["values"]
    mask=rasterize_parcel_mask(parcel,width=width,height=height,
        crs=red["crs"],transform=red["transform"])["mask"]
    total=clear=valid=0
    sums={"ndvi":0.0,"ndwi":0.0,"ndmi":0.0}
    counts={key:0 for key in sums}
    for i,inside in enumerate(mask):
        if not inside:
            continue
        total+=1
        qa=quality[i]
        if type(qa) is not int or not 0<=qa<=11:
            raise RangeFetchError("Invalid Sentinel-2 SCL classification")
        if not is_clear_pixel(PixelQuality(sensor=QualitySensor.sentinel_2,qa_value=qa)):
            continue
        clear+=1
        dn={band:bands[name]["values"][i] for name,band in MAPPING.items()}
        if any(type(v) is not int or not 0<=v<=65535 for v in dn.values()):
            raise RangeFetchError("Invalid Sentinel-2 digital number")
        try:
            sample=calibrate_reflectance(CalibrationInput(
                provider=PROVIDER,digital_numbers=dn,
                sentinel_quantification=quantification,sentinel_offsets=offsets))
            indices=calculate_indices(sample)
        except (ValueError,ArithmeticError):
            continue
        if any(getattr(indices,key) is None for key in sums):
            continue
        valid+=1
        for key in sums:
            sums[key]+=getattr(indices,key)
            counts[key]+=1
    return {"parcel_pixels":total,"clear_pixels":clear,"valid_pixels":valid,
            "mean_indices":{key:round(sums[key]/counts[key],6)
                            if counts[key] else None for key in sums},
            "index_pixel_counts":counts,"resampled_bands":aligned["resampled_bands"],
            "scl_resampled":bool(scl_alignment["resampled_bands"]),
            "parcel_mask_applied":True,"quality_mask_applied":True,
            "reflectance_calibrated":True,"calibration_metadata_verified":False,
            "source_checksum_verified":False,"provenance_verified":False}
