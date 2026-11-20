"""Bounded remote TIFF header probe; does not decode imagery or trust provenance."""
from .scim_cog_range_fetch import fetch_cog_range, RangeFetchError

def inspect_remote_tiff_header(url: str, *, approved: bool = False, opener=None) -> dict:
    """Read exactly 16 bytes and validate classic TIFF / BigTIFF header structure."""
    response = fetch_cog_range(url, 0, 16, approved=approved, opener=opener)
    header = response["data"]
    if header[:2] == b"II":
        order = "little"
    elif header[:2] == b"MM":
        order = "big"
    else:
        raise RangeFetchError("Invalid TIFF byte order")
    version = int.from_bytes(header[2:4], order)
    if version == 42:
        offset = int.from_bytes(header[4:8], order)
        variant = "TIFF"
        minimum = 8
    elif version == 43:
        if int.from_bytes(header[4:6], order) != 8 or header[6:8] != bytes(2):
            raise RangeFetchError("Unsupported BigTIFF header layout")
        offset = int.from_bytes(header[8:16], order)
        variant = "BigTIFF"
        minimum = 16
    else:
        raise RangeFetchError("Unsupported TIFF version")
    if offset < minimum or offset >= response["total_bytes"]:
        raise RangeFetchError("Invalid first image directory offset")
    return {"format": variant, "byte_order": order, "first_ifd_offset": offset,
            "object_bytes": response["total_bytes"], "header_verified": True,
            "cog_layout_verified": False, "pixel_data_read": False,
            "source_checksum_verified": False, "provenance_verified": False}
