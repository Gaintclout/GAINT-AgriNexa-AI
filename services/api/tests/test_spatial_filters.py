import pytest
from fastapi import HTTPException
from app.spatial_filters import normalize_filter
from app.main import app

def test_filter_normalization():
    assert normalize_filter("  TG001  ", "village_code") == "TG001"
    assert normalize_filter(None, "external_id") is None

@pytest.mark.parametrize("value", ["", "  ", "x" * 101])
def test_invalid_filter(value):
    with pytest.raises(HTTPException) as exc:
        normalize_filter(value, "village_code")
    assert exc.value.status_code == 422

def test_spatial_api_exposes_filters():
    parameters = app.openapi()["paths"]["/api/v1/gis/parcels/geojson"]["get"]["parameters"]
    names = {item["name"] for item in parameters}
    assert {"village_code", "external_id", "west", "south", "east", "north"}.issubset(names)
