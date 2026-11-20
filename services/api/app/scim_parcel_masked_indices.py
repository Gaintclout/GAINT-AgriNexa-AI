"""Parcel-masked vegetation indices from co-registered calibrated reflectance.

Pure offline computation. All four bands must have the same pixel grid.
Mask pixels must come from a separately validated parcel rasterization;
this function does not infer polygon coverage from a bounding box.
"""
from math import isfinite
from .scim_indices import ReflectanceSample, calculate_indices
from .scim_cog_range_fetch import RangeFetchError

MAX_ANALYSIS_PIXELS=1_000_000

def analyze_masked_reflectance(red,nir,green,swir1,mask,*,nodata=None):
    bands=(red,nir,green,swir1)
    if not all(isinstance(b,(list,tuple)) for b in bands):
        raise RangeFetchError("Reflectance bands must be pixel sequences")
    if not isinstance(mask,(list,tuple)):
        raise RangeFetchError("Parcel mask must be a pixel sequence")
    size=len(mask)
    if not 1<=size<=MAX_ANALYSIS_PIXELS or any(len(b)!=size for b in bands):
        raise RangeFetchError("Bands and parcel mask must have aligned lengths")
    if any(type(m) is not bool for m in mask):
        raise RangeFetchError("Parcel mask must contain booleans")
    if nodata is not None and (type(nodata) not in (float,int) or not isfinite(nodata)):
        raise RangeFetchError("Invalid nodata sentinel")
    totals={"ndvi":0.0,"ndwi":0.0,"ndmi":0.0}
    counts={"ndvi":0,"ndwi":0,"ndmi":0}
    covered=0
    valid=0
    for i,inside in enumerate(mask):
        if not inside:
            continue
        covered+=1
        values=[b[i] for b in bands]
        if any(type(v) not in (int,float) or not isfinite(v) or
               v<0 or v>1 or (nodata is not None and v==nodata)
               for v in values):
            continue
        valid+=1
        indices=calculate_indices(ReflectanceSample(
            red=values[0],nir=values[1],green=values[2],swir1=values[3]))
        for key in totals:
            value=getattr(indices,key)
            if value is not None:
                totals[key]+=value
                counts[key]+=1
    return {"parcel_pixels":covered,"valid_pixels":valid,
            "invalid_pixels":covered-valid,
            "mean_indices":{key:round(totals[key]/counts[key],6)
                            if counts[key] else None for key in totals},
            "index_pixel_counts":counts,"parcel_mask_applied":True,
            "reflectance_calibration_required":True,
            "source_checksum_verified":False,"provenance_verified":False}
