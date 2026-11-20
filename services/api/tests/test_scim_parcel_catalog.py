"""SCIM parcel-to-STAC search tests using the Siddipet synthetic fixture."""
import json
from datetime import datetime, timezone
from pathlib import Path
import pytest
from app.scim_parcel_catalog import parcel_bbox, parcel_catalog_searches

FIXTURE = Path(__file__).parent / "fixtures" / "scim_siddipet_sample_parcel.geojson"

def polygon():
    return json.loads(FIXTURE.read_text())

def test_siddipet_polygon_bounds():
    assert parcel_bbox(polygon()) == (
        78.8595274, 18.1195508, 78.8604726, 18.1204492)

def test_searches_cover_all_sensor_families():
    results = parcel_catalog_searches(
        polygon(), datetime(2026, 1, 1, tzinfo=timezone.utc),
        datetime(2026, 2, 1, tzinfo=timezone.utc))
    assert set(results) == {"sentinel-2", "landsat-8", "landsat-9"}
    assert results["sentinel-2"]["collections"] == ["sentinel-2-l2a"]
    assert results["landsat-8"]["collections"] == ["landsat-c2-l2"]
    assert results["landsat-9"]["bbox"] == list(parcel_bbox(polygon()))

def test_unclosed_polygon_rejected():
    geometry = polygon()
    geometry["coordinates"][0].pop()
    with pytest.raises(ValueError, match="closed"):
        parcel_bbox(geometry)

def test_nonfinite_coordinates_rejected():
    geometry = polygon()
    geometry["coordinates"][0][1][0] = float("nan")
    with pytest.raises(ValueError, match="coordinate"):
        parcel_bbox(geometry)

def test_invalid_date_range_rejected():
    when = datetime(2026, 1, 1, tzinfo=timezone.utc)
    with pytest.raises(ValueError):
        parcel_catalog_searches(polygon(), when, when)
