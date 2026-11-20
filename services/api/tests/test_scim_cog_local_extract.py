"""Offline synthetic GeoTIFF crop regression tests."""
from hashlib import sha256
import numpy as np
import pytest
import rasterio
from rasterio.transform import from_origin
from app.scim_cog_local_extract import extract_local_parcel_window

PARCEL = {"type": "Polygon", "coordinates": [[[80.05, 19.90],
          [80.10, 19.90], [80.10, 19.85], [80.05, 19.85], [80.05, 19.90]]]}

def prepare(tmp_path):
    source = tmp_path / "source"
    output = tmp_path / "output"
    source.mkdir()
    output.mkdir()
    with rasterio.open(source / "band.tif", "w", driver="GTiff",
                       width=20, height=20, count=1, dtype="uint16",
                       crs="EPSG:4326", transform=from_origin(80, 20, .01, .01)) as dst:
        dst.write(np.arange(400, dtype="uint16").reshape(20, 20), 1)
    return source, output

def test_crop_georeferencing_and_digest(tmp_path):
    source, output = prepare(tmp_path)
    target = output / "crop.tif"
    report = extract_local_parcel_window(source, "band.tif", PARCEL, target, margin_pixels=0)
    assert report["sha256"] == sha256(target.read_bytes()).hexdigest()
    assert not report["source_checksum_verified"]
    assert not report["network_access"]
    with rasterio.open(target) as crop:
        assert crop.crs.to_epsg() == 4326
        assert crop.width * crop.height <= 10000
        assert crop.dtypes[0] == "uint16"
        with rasterio.open(source / "band.tif") as original:
            window = report["window"]
            expected = original.read(1)[window["row_off"]:window["row_off"]+window["height"],
                                        window["col_off"]:window["col_off"]+window["width"]]
        assert np.array_equal(crop.read(1), expected)

def test_existing_output_preserved(tmp_path):
    source, output = prepare(tmp_path)
    target = output / "crop.tif"
    target.write_bytes(b"existing")
    with pytest.raises(FileExistsError):
        extract_local_parcel_window(source, "band.tif", PARCEL, target)
    assert target.read_bytes() == b"existing"

def test_distant_parcel_fails_without_output(tmp_path):
    source, output = prepare(tmp_path)
    distant = {"type": "Polygon", "coordinates": [[[81, 18], [81.1, 18],
               [81.1, 18.1], [81, 18.1], [81, 18]]]}
    with pytest.raises(ValueError, match="intersect"):
        extract_local_parcel_window(source, "band.tif", distant, output / "crop.tif")
    assert not (output / "crop.tif").exists()
