"""Rasterize a validated WGS84 parcel onto a bounded north-up pixel grid.

Pixel-center inclusion; boundaries count as inside. No network or filesystem
access. Caller-supplied grid georeferencing must be independently validated.
"""
from math import isfinite
from .scim_cog_range_fetch import RangeFetchError

MAX_MASK_PIXELS=1_000_000
MAX_RING_VERTICES=4096

def rasterize_parcel_mask(parcel,*,width,height,transform,crs):
    if (type(width) is not int or type(height) is not int or
            width<1 or height<1 or width*height>MAX_MASK_PIXELS):
        raise RangeFetchError("Invalid parcel mask pixel budget")
    if (not isinstance(transform,(list,tuple)) or len(transform)!=6 or
            any(type(v) not in (int,float) or not isfinite(v) for v in transform)):
        raise RangeFetchError("Invalid parcel grid transform")
    a,b,c,d,e,f=transform
    if a<=0 or e>=0 or b!=0 or d!=0:
        raise RangeFetchError("Only north-up nonrotated grids supported")
    if not isinstance(crs,str) or not (crs=="EPSG:4326" or
            (crs.startswith("EPSG:") and crs[5:].isdigit() and
             (32601<=int(crs[5:])<=32660 or 32701<=int(crs[5:])<=32760))):
        raise RangeFetchError("Unsupported parcel grid CRS")
    if not isinstance(parcel,dict) or parcel.get("type")!="Polygon":
        raise RangeFetchError("WGS84 Polygon required")
    rings=parcel.get("coordinates")
    if not isinstance(rings,list) or len(rings)!=1 or not isinstance(rings[0],list):
        raise RangeFetchError("Only simple polygons without holes supported")
    ring=rings[0]
    if not 4<=len(ring)<=MAX_RING_VERTICES or ring[0]!=ring[-1]:
        raise RangeFetchError("Invalid polygon ring")
    points=[]
    for pt in ring:
        if (not isinstance(pt,(list,tuple)) or len(pt)!=2 or
                any(type(v) not in (int,float) or not isfinite(v) for v in pt)):
            raise RangeFetchError("Invalid WGS84 coordinate")
        lon,lat=pt
        if not (-180<=lon<=180 and -90<=lat<=90):
            raise RangeFetchError("WGS84 coordinate outside bounds")
        points.append((lon,lat))
    try:
        from shapely.geometry import Polygon, Point
        from shapely.prepared import prep
        from pyproj import Transformer
        geometry=Polygon(points)
        if not geometry.is_valid or geometry.is_empty or geometry.area<=0:
            raise RangeFetchError("Invalid parcel geometry")
        if crs!="EPSG:4326":
            converter=Transformer.from_crs("EPSG:4326",crs,always_xy=True)
            projected=[converter.transform(x,y,errcheck=True) for x,y in points]
            if any(not isfinite(v) for pt in projected for v in pt):
                raise RangeFetchError("Nonfinite projected parcel")
            geometry=Polygon(projected)
            if not geometry.is_valid or geometry.is_empty or geometry.area<=0:
                raise RangeFetchError("Invalid projected parcel")
        prepared=prep(geometry)
        mask=[prepared.intersects(Point(c+(col+0.5)*a,f+(row+0.5)*e))
              for row in range(height) for col in range(width)]
    except RangeFetchError:
        raise
    except Exception as exc:
        raise RangeFetchError("Parcel rasterization failed") from exc
    return {"mask":mask,"width":width,"height":height,
            "parcel_pixels":sum(mask),"pixel_center_rule":True,
            "parcel_mask_applied":True,"georeferencing_source":"caller_supplied",
            "source_checksum_verified":False,"provenance_verified":False}
