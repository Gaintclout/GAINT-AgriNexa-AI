"""Reference comparison gate regression tests."""
from datetime import datetime, timezone
import pytest
from pydantic import ValidationError
from app.scim_reference_comparison import (
    SceneReference, ComparisonTolerance, compare_scene)

def reference(**overrides):
    data = dict(scene_id="L8-TEST", reference_source="independent QGIS export",
                reference_method="raster statistics", reference_timestamp=datetime.now(timezone.utc),
                parcel_pixels=10, clear_pixels=8, valid_pixels=7,
                ndvi_median=0.4, ndwi_median=-0.2, ndmi_median=0.1)
    data.update(overrides)
    return SceneReference(**data)

def actual(**overrides):
    data = dict(parcel_pixels=10, clear_pixels=8, valid_pixels=7,
                ndvi_median=0.41, ndwi_median=-0.19, ndmi_median=0.09)
    data.update(overrides)
    return data

def test_within_tolerance_passes():
    result = compare_scene(actual(), reference())
    assert result["passed"] is True
    assert result["status"] == "reference_comparison_only"

def test_missing_index_fails_closed():
    values = actual()
    del values["ndmi_median"]
    assert not compare_scene(values, reference())["passed"]

def test_outside_tolerance_fails():
    result = compare_scene(actual(ndvi_median=0.8), reference())
    assert result["checks"]["ndvi_median"] is False
    assert result["passed"] is False

def test_nonfinite_actual_fails():
    assert not compare_scene(actual(ndvi_median=float("nan")), reference())["passed"]

def test_pixel_count_mismatch_fails():
    assert not compare_scene(actual(valid_pixels=6), reference())["passed"]

def test_explicit_tolerance():
    assert compare_scene(actual(valid_pixels=6), reference(),
                         ComparisonTolerance(pixel_absolute=1))["passed"]

def test_invalid_reference_rejected():
    with pytest.raises(ValidationError):
        reference(valid_pixels=20)

def test_naive_reference_timestamp_rejected():
    with pytest.raises(ValidationError):
        reference(reference_timestamp=datetime(2026, 1, 1))

def test_inconsistent_actual_counts_fail_even_with_large_tolerance():
    result = compare_scene(
        actual(parcel_pixels=10, clear_pixels=8, valid_pixels=9),
        reference(), ComparisonTolerance(pixel_absolute=10))
    assert result["checks"]["pixel_count_consistency"] is False
    assert result["passed"] is False

def test_boolean_pixel_counts_rejected():
    result = compare_scene(actual(valid_pixels=True), reference())
    assert result["checks"]["pixel_count_consistency"] is False
    assert result["passed"] is False
