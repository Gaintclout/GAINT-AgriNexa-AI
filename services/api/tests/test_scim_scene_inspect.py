import pytest
from app.scim_scene_inspect import inspect_stac_scene
from app.scim_contracts import SatelliteProvider

URL = "https://sentinel-cogs.s3.us-west-2.amazonaws.com/example/band.tif"

def scene(collection="sentinel-2-l2a", platform="sentinel-2c"):
    return {"type": "Feature", "id": "SCENE_1", "collection": collection,
            "properties": {"platform": platform},
            "assets": {key: {"href": URL} for key in ("red", "green", "nir", "swir16", "scl")}}

def test_inspects_single_feature():
    report = inspect_stac_scene(scene(), SatelliteProvider.sentinel_2, "SCENE_1")
    assert report["all_urls_policy_passed"] is True
    assert report["metadata_only"] is True
    assert report["download_authorized"] is False

def test_inspects_feature_collection():
    report = inspect_stac_scene({"type": "FeatureCollection", "features": [scene()]},
                                SatelliteProvider.sentinel_2, "SCENE_1")
    assert report["scene_id"] == "SCENE_1"

@pytest.mark.parametrize("payload", [
    {}, {"type": "FeatureCollection", "features": []},
    {"type": "FeatureCollection", "features": [scene(), scene()]},
    scene(collection="landsat-c2-l2"),
    scene(platform="sentinel-2-unknown"),
])
def test_rejects_bad_scene(payload):
    with pytest.raises(ValueError):
        inspect_stac_scene(payload, SatelliteProvider.sentinel_2, "SCENE_1")

def test_rejects_wrong_scene_id():
    with pytest.raises(ValueError):
        inspect_stac_scene(scene(), SatelliteProvider.sentinel_2, "OTHER")
