import pytest
from app.scim_asset_review import review_assets
from app.scim_contracts import SatelliteProvider
from app.main import app

@pytest.mark.parametrize("provider,bands", [
    (SatelliteProvider.sentinel_2,("red","green","nir","swir16")),
    (SatelliteProvider.landsat_8,("red","green","nir08","swir16")),
    (SatelliteProvider.landsat_9,("red","green","nir08","swir16")),
])
def test_complete_asset_metadata(provider,bands):
    assets={key:{"href":"https://catalog.example/asset.tif"} for key in bands}
    result=review_assets(provider,assets)
    assert result["complete"] is True
    assert result["missing_bands"] == []

def test_missing_and_blank_assets():
    result=review_assets(SatelliteProvider.sentinel_2,{"red":{"href":" "},"nir":{"href":"asset"}})
    assert result["complete"] is False
    assert result["available_bands"] == ["nir"]
    assert set(result["missing_bands"]) == {"red","green","swir16"}

def test_rejects_non_object_assets():
    with pytest.raises(ValueError):
        review_assets(SatelliteProvider.sentinel_2,[])

def test_asset_review_route_documented():
    assert "/api/v1/scim/assets/review" in app.openapi()["paths"]
