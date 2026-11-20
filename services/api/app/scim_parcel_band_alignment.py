"""Conservative 2x nearest-neighbor alignment of calibrated reflectance grids.

Only exactly matching extents, north-up transforms, and CRS are accepted.
The target is the supplied red-band grid. No reprojection, interpolation,
cloud masking, or imagery retrieval occurs. Coarse pixels are replicated,
not interpreted as additional independent measurements.
"""
from math import isfinite
from .scim_cog_range_fetch import RangeFetchError
from .scim_parcel_registered_analysis import (
    REQUIRED_BANDS, MAX_GRID_PIXELS, analyze_registered_parcel_bands)

def align_reflectance_bands(bands):
    if not isinstance(bands,dict) or set(bands)!=set(REQUIRED_BANDS):
        raise RangeFetchError("Exactly four reflectance bands required")
    def validate(grid):
        if not isinstance(grid,dict):
            raise RangeFetchError("Invalid band grid")
        w,h=grid.get("width"),grid.get("height")
        if (type(w) is not int or type(h) is not int or w<1 or h<1
                or w*h>MAX_GRID_PIXELS):
            raise RangeFetchError("Invalid band pixel budget")
        t=grid.get("transform")
        if (not isinstance(t,(tuple,list)) or len(t)!=6 or
                any(type(v) not in (int,float) or not isfinite(v) for v in t)):
            raise RangeFetchError("Invalid band affine transform")
        a,b,c,d,e,f=t
        if a<=0 or e>=0 or b!=0 or d!=0:
            raise RangeFetchError("Only north-up band grids supported")
        if not isinstance(grid.get("crs"),str) or not grid["crs"]:
            raise RangeFetchError("Missing band CRS")
        values=grid.get("values")
        if not isinstance(values,(list,tuple)) or len(values)!=w*h:
            raise RangeFetchError("Band pixel count mismatch")
        return w,h,tuple(t)
    target=bands["red"]
    tw,th,tt=validate(target)
    output={}
    resampled=[]
    for name in REQUIRED_BANDS:
        grid=bands[name]
        w,h,t=validate(grid)
        if grid["crs"]!=target["crs"]:
            raise RangeFetchError("Band CRS mismatch; reprojection unsupported")
        factor=tw//w if tw%w==0 else 0
        if factor not in (1,2) or th!=h*factor:
            raise RangeFetchError("Only identical or exact 2x band alignment supported")
        if (t[2]!=tt[2] or t[5]!=tt[5] or t[0]!=tt[0]*factor
                or t[4]!=tt[4]*factor):
            raise RangeFetchError("Band origins or extents do not align")
        if factor==1:
            pixels=list(grid["values"])
        else:
            pixels=[grid["values"][(row//2)*w+(col//2)]
                    for row in range(th) for col in range(tw)]
            resampled.append(name)
        output[name]={"width":tw,"height":th,"crs":target["crs"],
                      "transform":tt,"values":pixels}
    return {"bands":output,"resampled_bands":resampled,
            "resampling_method":"nearest_neighbor_2x",
            "band_coregistration_verified":True,
            "source_checksum_verified":False,"provenance_verified":False}

def analyze_aligned_parcel_bands(parcel,bands,*,nodata=None):
    aligned=align_reflectance_bands(bands)
    result=analyze_registered_parcel_bands(parcel,aligned["bands"],nodata=nodata)
    return {**result,"resampled_bands":aligned["resampled_bands"],
            "resampling_method":aligned["resampling_method"]}
