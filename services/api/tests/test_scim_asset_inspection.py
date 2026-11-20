import pytest
from app.scim_asset_inspection import inspect_scene_assets
from app.scim_contracts import SatelliteProvider

SAFE = "https://sentinel-cogs.s3.us-west-2.amazonaws.com/example/band.tif"

def test_sentinel_requires_quality_mask():
    assets = {key: {"href": SAFE} for key in ("red", "green", "nir", "swir16")}
    report = inspect_scene_assets(SatelliteProvider.sentinel_2, {"id": "scene-1", "assets": assets})
    assert report["assets"]["scl"]["status"] == "missing"
    assert report["all_urls_policy_passed"] is False
    assert report["download_authorized"] is False

def test_landsat_quality_mask_and_url_policy():
    assets = {key: {"href": SAFE} for key in ("red", "green", "nir08", "swir16", "qa_pixel")}
    report = inspect_scene_assets(SatelliteProvider.landsat_8, {"id": "scene-2", "assets": assets})
    assert report["all_urls_policy_passed"] is True
    assert report["checksum_verified"] is False
    assert report["provenance_verified"] is False
    assert report["real_scene_validation_complete"] is False

def test_rejects_untrusted_host_without_exposing_url():
    assets = {key: {"href": "https://untrusted.example/test.tif"} for key in ("red", "green", "nir", "swir16", "scl")}
    report = inspect_scene_assets(SatelliteProvider.sentinel_2, {"assets": assets})
    assert all(value["status"] == "untrusted_url" for value in report["assets"].values())
    assert "untrusted.example" not in str(report)

@pytest.mark.parametrize("feature", [None, {}, {"assets": []}])
def test_invalid_feature(feature):
    with pytest.raises(ValueError):
        inspect_scene_assets(SatelliteProvider.sentinel_2, feature)
