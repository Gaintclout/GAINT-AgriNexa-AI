from datetime import datetime, timezone, timedelta
import pytest
from pydantic import ValidationError
from app.scim_catalog import CatalogSearch, build_stac_search
from app.main import app

def search(**overrides):
    values = dict(provider="sentinel-2", west=78, south=17, east=79, north=18,
                  start=datetime(2026, 9, 1, tzinfo=timezone.utc),
                  end=datetime(2026, 10, 1, tzinfo=timezone.utc),
                  max_cloud_percent=25, limit=10)
    values.update(overrides)
    return CatalogSearch(**values)

def test_stac_search_payload():
    result = build_stac_search(search())
    assert result["collections"] == ["sentinel-2-l2a"]
    assert result["bbox"] == [78, 17, 79, 18]
    assert result["query"]["eo:cloud_cover"]["lte"] == 25
    assert result["limit"] == 10

@pytest.mark.parametrize("provider,collection", [
    ("landsat-8","landsat-c2-l2"),("landsat-9","landsat-c2-l2"),
])
def test_landsat_collections(provider,collection):
    assert build_stac_search(search(provider=provider))["collections"] == [collection]

@pytest.mark.parametrize("changes", [
    {"west": 80}, {"north": 16}, {"max_cloud_percent": 101},
    {"start": datetime(2026, 10, 2, tzinfo=timezone.utc)},
    {"start": datetime(2026, 9, 1)},
    {"end": datetime.now(timezone.utc) + timedelta(days=1)},
    {"end": datetime(2026, 10, 1), "limit": 101},
])
def test_invalid_search_rejected(changes):
    with pytest.raises(ValidationError):
        search(**changes)

def test_preview_endpoint_documented():
    assert "/api/v1/scim/catalog/search-preview" in app.openapi()["paths"]

def test_search_window_rejects_fractional_day_over_limit():
    with pytest.raises(ValidationError):
        search(start=datetime(2025,9,30,tzinfo=timezone.utc),
               end=datetime(2026,10,1,0,0,1,tzinfo=timezone.utc))
