"""Validate caller-supplied decoded grid metadata against probed GeoTIFF tags.

No network requests are made here. A pinned caller must supply independently
probed tile table and georeferencing dictionaries from the same object version.
This validates consistency, not cryptographic authenticity or provenance.
"""
from math import isfinite
from .scim_cog_range_fetch import RangeFetchError
from .scim_cog_decoded_grid_assembly import assemble_decoded_tile_grid

def assemble_verified_geotiff_grid(decoded,table,georef,metadata):
    if not all(isinstance(x,dict) for x in (decoded,table,georef,metadata)):
        raise RangeFetchError("GeoTIFF probe results and raster metadata required")
    required={"width","height","tile_width","tile_height","crs","transform"}
    if set(metadata)!=required:
        raise RangeFetchError("Incomplete raster metadata")
    for key in ("width","height","tile_width","tile_height"):
        if type(table.get(key)) is not int or table[key]!=metadata[key]:
            raise RangeFetchError("GeoTIFF tile geometry mismatch")
    if georef.get("crs")!=metadata["crs"]:
        raise RangeFetchError("GeoTIFF CRS mismatch")
    observed=georef.get("transform")
    declared=metadata["transform"]
    if (not isinstance(observed,(tuple,list)) or
            not isinstance(declared,(tuple,list)) or
            len(observed)!=6 or len(declared)!=6 or
            any(type(v) not in (int,float) or not isfinite(v)
                for v in (*observed,*declared)) or
            tuple(observed)!=tuple(declared)):
        raise RangeFetchError("GeoTIFF affine transform mismatch")
    if (type(table.get("object_bytes")) is not int or
            type(georef.get("object_bytes")) is not int or
            table["object_bytes"]!=georef["object_bytes"]):
        raise RangeFetchError("GeoTIFF object size mismatch")
    if decoded.get("object_version_pinned") is not True or decoded.get("metadata_version_pinned") is not True:
        raise RangeFetchError("Pinned decoded object required")
    grid=assemble_decoded_tile_grid(decoded,**metadata)
    return {**grid,"georeferencing_source":"geotiff_probe",
            "georeferencing_consistency_checked":True,
            "georeferencing_authenticated":False,
            "source_checksum_verified":False,"provenance_verified":False}
