"""Assemble a complete, bounded decoded TIFF tile grid without network access.

Requires full tile coverage of a caller-declared raster and a north-up
georeference. Rejects duplicates, gaps, unexpected tiles and truncated pixels.
The resulting grid is caller-georeferenced; this adapter does not authenticate
GeoTIFF metadata or the scene's source.
"""
from math import isfinite
from .scim_cog_range_fetch import RangeFetchError

MAX_GRID_PIXELS=1_000_000

def assemble_decoded_tile_grid(decoded,*,width,height,tile_width,tile_height,
                               crs,transform):
    dims=(width,height,tile_width,tile_height)
    if (any(type(v) is not int or v<1 for v in dims)
            or width*height>MAX_GRID_PIXELS):
        raise RangeFetchError("Invalid raster dimensions or pixel budget")
    if (not isinstance(crs,str) or not crs or
            not isinstance(transform,(tuple,list)) or len(transform)!=6 or
            any(type(v) not in (int,float) or not isfinite(v) for v in transform)):
        raise RangeFetchError("Invalid raster georeferencing")
    a,b,c,d,e,f=transform
    if a<=0 or e>=0 or b!=0 or d!=0:
        raise RangeFetchError("Only north-up nonrotated grids supported")
    if not isinstance(decoded,dict) or decoded.get("pixel_values_decoded") is not True:
        raise RangeFetchError("Decoded tile result required")
    if (decoded.get("object_version_pinned") is not True or
            decoded.get("metadata_version_pinned") is not True):
        raise RangeFetchError("Pinned decoded tile result required")
    tiles=decoded.get("tiles")
    cols=(width+tile_width-1)//tile_width
    rows=(height+tile_height-1)//tile_height
    if not isinstance(tiles,list) or len(tiles)!=cols*rows or len(tiles)>16:
        raise RangeFetchError("Complete bounded tile coverage required")
    values=[None]*(width*height)
    seen=set()
    for tile in tiles:
        if not isinstance(tile,dict):
            raise RangeFetchError("Invalid decoded tile")
        index,row,col=tile.get("index"),tile.get("row"),tile.get("column")
        if (any(type(v) is not int for v in (index,row,col)) or
                not 0<=row<rows or not 0<=col<cols or index!=row*cols+col
                or index in seen):
            raise RangeFetchError("Invalid or duplicate tile position")
        seen.add(index)
        pixels=tile.get("pixels")
        if not isinstance(pixels,list) or len(pixels)!=tile_width*tile_height:
            raise RangeFetchError("Invalid decoded tile pixel count")
        for local_row in range(tile_height):
            dest_row=row*tile_height+local_row
            if dest_row>=height:
                break
            for local_col in range(tile_width):
                dest_col=col*tile_width+local_col
                if dest_col>=width:
                    break
                value=pixels[local_row*tile_width+local_col]
                if type(value) is not int or not 0<=value<=65535:
                    raise RangeFetchError("Invalid decoded integer pixel")
                values[dest_row*width+dest_col]=value
    if any(value is None for value in values):
        raise RangeFetchError("Incomplete decoded raster coverage")
    return {"width":width,"height":height,"crs":crs,
            "transform":tuple(transform),"values":values,
            "decoded":True,"version_pinned":True,
            "georeferencing_source":"caller_supplied",
            "source_checksum_verified":False,"provenance_verified":False}
