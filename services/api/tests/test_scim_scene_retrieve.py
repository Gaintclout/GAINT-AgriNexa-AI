import json
import pytest
from app.scim_contracts import SatelliteProvider
from app.scim_discovery import CatalogUnavailable, EARTH_SEARCH_URL
from app.scim_scene_retrieve import retrieve_scene_report, parse_exact_scene

URL = "https://sentinel-cogs.s3.us-west-2.amazonaws.com/example/band.tif"

def feature():
    return {"type": "Feature", "id": "SCENE_1", "collection": "sentinel-2-l2a",
            "properties": {"platform": "sentinel-2c"},
            "assets": {k: {"href": URL} for k in ("red", "green", "nir", "swir16", "scl")}}

def payload(features=None):
    return {"type": "FeatureCollection", "features": [feature()] if features is None else features}

class FakeResponse:
    status = 200
    def __init__(self, data):
        self.data = data
    def __enter__(self):
        return self
    def __exit__(self, *args):
        pass
    def read(self, size):
        return self.data[:size]

class FakeOpener:
    def __init__(self, data):
        self.data = data
    def open(self, request, timeout):
        assert request.full_url == EARTH_SEARCH_URL
        assert request.get_method() == "POST"
        assert json.loads(request.data) == {"collections": ["sentinel-2-l2a"], "ids": ["SCENE_1"], "limit": 1}
        assert timeout == 10
        return FakeResponse(self.data)

def test_exact_scene_retrieval_without_download():
    report = retrieve_scene_report(SatelliteProvider.sentinel_2, "SCENE_1",
                                   opener=FakeOpener(json.dumps(payload()).encode()))
    assert report["all_urls_policy_passed"]
    assert not report["download_authorized"]
    assert report["metadata_only"]

@pytest.mark.parametrize("scene_id", ["", "bad/id", "a" * 201, "x y"])
def test_rejects_bad_scene_id(scene_id):
    with pytest.raises(ValueError):
        retrieve_scene_report(SatelliteProvider.sentinel_2, scene_id, opener=FakeOpener(b"{}"))

@pytest.mark.parametrize("data", [
    {}, {"type": "FeatureCollection", "features": []},
    payload([feature(), feature()]),
    payload([dict(feature(), id="OTHER")]),
])
def test_rejects_bad_catalog_response(data):
    with pytest.raises(CatalogUnavailable):
        parse_exact_scene(data, SatelliteProvider.sentinel_2, "SCENE_1")

def test_rejects_oversized_response():
    with pytest.raises(CatalogUnavailable):
        retrieve_scene_report(SatelliteProvider.sentinel_2, "SCENE_1",
                              opener=FakeOpener(b"x" * 1_000_002))
