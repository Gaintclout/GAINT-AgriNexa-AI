from datetime import datetime, timezone
from app.scim_catalog import CatalogSearch
from app.scim_discovery import CatalogResults, DiscoveredScene, parse_stac_response
from app.scim_ranking import rank_scenes
from app.main import app

def search():
    return CatalogSearch(provider="sentinel-2",west=78,south=17,east=79,north=18,
                         start=datetime(2026,9,1,tzinfo=timezone.utc),
                         end=datetime(2026,10,1,tzinfo=timezone.utc))

def feature(scene_id, cloud, complete):
    assets={key:{"href":"metadata-only"} for key in ("red","green","nir","swir16")} if complete else {}
    return {"id":scene_id,"collection":"sentinel-2-l2a","bbox":[78,17,79,18],
            "properties":{"datetime":"2026-09-10T10:00:00Z","eo:cloud_cover":cloud},"assets":assets}

def test_discovery_includes_band_review_without_urls():
    result=parse_stac_response({"type":"FeatureCollection","features":[feature("S2-A",10,True)]},search())
    scene=result.scenes[0]
    assert scene.assets_complete is True
    assert scene.missing_bands == []
    assert "href" not in scene.model_dump_json()

def test_missing_assets_reported():
    result=parse_stac_response({"type":"FeatureCollection","features":[feature("S2-B",5,False)]},search())
    assert result.scenes[0].assets_complete is False
    assert set(result.scenes[0].missing_bands)=={"red","green","nir","swir16"}

def test_rank_complete_before_cloudier_incomplete():
    result=parse_stac_response({"type":"FeatureCollection","features":[feature("incomplete",0,False),feature("complete",30,True)]},search())
    assert [scene.scene_id for scene in rank_scenes(result)] == ["complete","incomplete"]

def test_ranked_route_documented():
    assert "/api/v1/scim/catalog/discover-ranked" in app.openapi()["paths"]
