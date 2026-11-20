"""SCIM offline batch gate tests; no network or actual satellite datasets."""
from datetime import datetime, timezone
import json
from unittest.mock import patch
from app.scim_batch_validation import SceneCase, ValidationBatch, validate_batch

def make_case(root, provider, scene_id):
    folder = root / scene_id
    folder.mkdir()
    manifest = folder / "manifest.json"
    reference = folder / "reference.json"
    parcel = folder / "parcel.json"
    bands = (("B04", "B08", "B03", "B11") if provider == "sentinel-2"
             else ("SR_B4", "SR_B5", "SR_B3", "SR_B6"))
    manifest.write_text(json.dumps({
        "provider": provider, "scene_id": scene_id,
        "qa": {"filename": "qa.tif", "sha256": "0" * 64},
        "bands": {band: {"filename": band + ".tif", "sha256": "0" * 64}
                  for band in bands}}))
    reference.write_text(json.dumps({
        "scene_id": scene_id, "reference_source": "independent GIS export",
        "reference_method": "zonal raster statistics",
        "reference_timestamp": datetime.now(timezone.utc).isoformat(),
        "parcel_pixels": 10, "clear_pixels": 8, "valid_pixels": 7,
        "ndvi_median": .4, "ndwi_median": -.2, "ndmi_median": .1}))
    parcel.write_text('{"type":"Polygon","coordinates":[]}')
    return SceneCase(root=folder, manifest=manifest, reference=reference, parcel=parcel)

def summary(*args, **kwargs):
    return {"parcel_pixels": 10, "clear_pixels": 8, "valid_pixels": 7,
            "ndvi_median": .4, "ndwi_median": -.2, "ndmi_median": .1}

def test_two_sensor_families_pass(tmp_path):
    batch = ValidationBatch(cases=[make_case(tmp_path, "sentinel-2", "S2-A"),
                                   make_case(tmp_path, "landsat-8", "L8-A")])
    with patch("app.scim_batch_validation.validate_scene", side_effect=summary):
        report = validate_batch(batch)
    assert report["passed"]
    assert report["coverage"] == {"sentinel_2": True, "landsat": True}

def test_two_sentinel_scenes_do_not_satisfy_landsat(tmp_path):
    batch = ValidationBatch(cases=[make_case(tmp_path, "sentinel-2", "S2-A"),
                                   make_case(tmp_path, "sentinel-2", "S2-B")])
    with patch("app.scim_batch_validation.validate_scene", side_effect=summary):
        report = validate_batch(batch)
    assert not report["passed"]
    assert not report["coverage"]["landsat"]

def test_reference_mismatch_rejected(tmp_path):
    batch = ValidationBatch(cases=[make_case(tmp_path, "sentinel-2", "S2-A"),
                                   make_case(tmp_path, "landsat-8", "L8-A")])
    payload = json.loads(batch.cases[0].reference.read_text())
    payload["scene_id"] = "WRONG"
    batch.cases[0].reference.write_text(json.dumps(payload))
    import pytest
    with pytest.raises(ValueError, match="scene ID"):
        validate_batch(batch)

def test_failed_reference_comparison_blocks_batch(tmp_path):
    batch = ValidationBatch(cases=[make_case(tmp_path, "sentinel-2", "S2-A"),
                                   make_case(tmp_path, "landsat-8", "L8-A")])
    def differing(*args, **kwargs):
        value = summary()
        value["ndvi_median"] = .9
        return value
    with patch("app.scim_batch_validation.validate_scene", side_effect=differing):
        report = validate_batch(batch)
    assert not report["passed"]

def test_duplicate_sensor_scene_rejected(tmp_path):
    first = make_case(tmp_path, "sentinel-2", "S2-A")
    second = make_case(tmp_path, "landsat-8", "L8-A")
    payload = json.loads(second.manifest.read_text())
    payload["provider"] = "sentinel-2"
    payload["scene_id"] = "S2-A"
    payload["bands"] = {band: {"filename": band + ".tif", "sha256": "0" * 64}
                        for band in ("B04", "B08", "B03", "B11")}
    second.manifest.write_text(json.dumps(payload))
    ref = json.loads(second.reference.read_text())
    ref["scene_id"] = "S2-A"
    second.reference.write_text(json.dumps(ref))
    with patch("app.scim_batch_validation.validate_scene", side_effect=summary):
        import pytest
        with pytest.raises(ValueError, match="Duplicate"):
            validate_batch(ValidationBatch(cases=[first, second]))
