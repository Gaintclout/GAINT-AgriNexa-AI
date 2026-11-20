from datetime import datetime, timezone
import pytest
from app.scim_catalog import CatalogSearch
from app.scim_discovery import CatalogUnavailable, parse_stac_response
from app.main import app

def search(provider="sentinel-2"):
    return CatalogSearch(provider=provider, west=78, south=17, east=79, north=18,
                         start=datetime(2026,9,1,tzinfo=timezone.utc),
                         end=datetime(2026,10,1,tzinfo=timezone.utc), limit=5)

def feature(collection="sentinel-2-l2a",platform="sentinel-2a"):
    return {"type":"Feature","id":"S2_001","collection":collection,
            "bbox":[78,17,79,18],
            "properties":{"datetime":"2026-09-10T10:00:00Z","eo:cloud_cover":12,"platform":platform}}

def test_parses_sentinel_metadata_without_assets():
    result=parse_stac_response({"type":"FeatureCollection","features":[feature()]},search())
    assert result.returned == 1
    assert result.scenes[0].scene_id == "S2_001"
    assert not hasattr(result.scenes[0],"assets")

def test_landsat_platform_filter():
    payload={"type":"FeatureCollection","features":[feature("landsat-c2-l2","landsat-8")]}
    assert parse_stac_response(payload,search("landsat-8")).returned == 1
    assert parse_stac_response(payload,search("landsat-9")).returned == 0

def test_pagination_marker():
    payload={"type":"FeatureCollection","features":[],"links":[{"rel":"next","href":"https://example.com"}]}
    assert parse_stac_response(payload,search()).truncated is True

@pytest.mark.parametrize("payload",[
    {},{"type":"FeatureCollection","features":{}},
    {"type":"FeatureCollection","features":[{}]},
    {"type":"FeatureCollection","features":[feature()]*6},
])
def test_rejects_invalid_catalog_data(payload):
    with pytest.raises(CatalogUnavailable):
        parse_stac_response(payload,search())

def test_discovery_route_documented():
    assert "/api/v1/scim/catalog/discover" in app.openapi()["paths"]

def test_rejects_naive_acquisition_time():
    item=feature()
    item["properties"]["datetime"]="2026-09-10T10:00:00"
    with pytest.raises(CatalogUnavailable):
        parse_stac_response({"type":"FeatureCollection","features":[item]},search())

def test_rejects_reversed_bounds():
    item=feature()
    item["bbox"]=[79,17,78,18]
    with pytest.raises(CatalogUnavailable):
        parse_stac_response({"type":"FeatureCollection","features":[item]},search())

def test_excludes_scene_outside_requested_dates():
    item=feature()
    item["properties"]["datetime"]="2026-08-10T10:00:00Z"
    assert parse_stac_response({"type":"FeatureCollection","features":[item]},search()).returned == 0

def test_excludes_scene_above_cloud_threshold():
    item=feature()
    item["properties"]["eo:cloud_cover"]=95
    assert parse_stac_response({"type":"FeatureCollection","features":[item]},search()).returned == 0

def test_rejects_non_mapping_assets():
    item=feature()
    item["assets"]=[]
    with pytest.raises(CatalogUnavailable):
        parse_stac_response({"type":"FeatureCollection","features":[item]},search())

def test_catalog_does_not_follow_invalid_feature_types():
    with pytest.raises(CatalogUnavailable):
        parse_stac_response({"type":"FeatureCollection","features":["invalid"]},search())

def test_catalog_reports_incomplete_assets_without_exposing_links():
    item=feature()
    item["assets"]={"red":{"href":"https://example.test/red.tif"}}
    result=parse_stac_response({"type":"FeatureCollection","features":[item]},search())
    scene=result.scenes[0]
    assert scene.assets_complete is False
    assert "green" in scene.missing_bands
    assert "href" not in scene.model_dump_json()

def test_missing_cloud_metadata_is_not_treated_as_clear():
    item=feature()
    item["properties"].pop("eo:cloud_cover")
    result=parse_stac_response({"type":"FeatureCollection","features":[item]},search())
    assert result.returned == 0
