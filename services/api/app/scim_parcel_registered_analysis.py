"""Strict co-registration and parcel masking for calibrated reflectance grids.

No resampling is attempted: different CRS, affine transform, dimensions, or
band layout fail closed. All input bands must already be calibrated to [0,1].
No network, persistence, or source provenance verification is performed.
"""
from math import isfinite
from .scim_cog_range_fetch import RangeFetchError
from .scim_parcel_polygon_mask import rasterize_parcel_mask
from .scim_parcel_masked_indices import analyze_masked_reflectance

REQUIRED_BANDS=("red","nir","green","swir1")
MAX_GRID_PIXELS=1_000_000

def analyze_registered_parcel_bands(parcel,bands,*,nodata=None):
    if not isinstance(bands,dict) or set(bands)!=set(REQUIRED_BANDS):
        raise RangeFetchError("Exactly red, nir, green and swir1 bands required")
    reference=None
    values={}
    for name in REQUIRED_BANDS:
        grid=bands[name]
        if not isinstance(grid,dict):
            raise RangeFetchError("Invalid reflectance grid")
        width,height=grid.get("width"),grid.get("height")
        if (type(width) is not int or type(height) is not int or
                width<1 or height<1 or width*height>MAX_GRID_PIXELS):
            raise RangeFetchError("Invalid reflectance grid dimensions")
        crs=grid.get("crs")
        transform=grid.get("transform")
        if (not isinstance(crs,str) or
                not isinstance(transform,(tuple,list)) or len(transform)!=6 or
                any(type(v) not in (int,float) or not isfinite(v) for v in transform)):
            raise RangeFetchError("Invalid reflectance georeferencing")
        registration=(width,height,crs,tuple(transform))
        if reference is None:
            reference=registration
        elif registration!=reference:
            raise RangeFetchError("Reflectance bands are not co-registered")
        pixels=grid.get("values")
        if not isinstance(pixels,(tuple,list)) or len(pixels)!=width*height:
            raise RangeFetchError("Reflectance pixel count mismatch")
        values[name]=pixels
    width,height,crs,transform=reference
    rasterized=rasterize_parcel_mask(
        parcel,width=width,height=height,transform=transform,crs=crs)
    result=analyze_masked_reflectance(
        values["red"],values["nir"],values["green"],values["swir1"],
        rasterized["mask"],nodata=nodata)
    return {**result,"width":width,"height":height,"crs":crs,
            "band_coregistration_verified":True,
            "georeferencing_source":"caller_supplied",
            "pixel_center_rule":True}
