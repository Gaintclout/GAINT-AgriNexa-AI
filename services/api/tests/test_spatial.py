import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient
from app.main import app
from app.spatial import check_bbox, parcel_features
from app.security import Principal, Role

def test_valid_bbox():
    check_bbox(78.0, 17.0, 79.0, 18.0)

@pytest.mark.parametrize("bbox", [
    (79, 17, 78, 18),
    (78, 18, 79, 17),
    (-181, 17, 79, 18),
    (78, 17, 181, 18),
    (78, -91, 79, 18),
    (78, 17, 79, 91),
    (float("nan"), 17, 79, 18),
])
def test_invalid_bbox(bbox):
    with pytest.raises(HTTPException) as error:
        check_bbox(*bbox)
    assert error.value.status_code == 422

def test_map_layer_requires_authentication():
    response = TestClient(app).get("/api/v1/gis/parcels/geojson", params={
        "west": 78, "south": 17, "east": 79, "north": 18
    })
    assert response.status_code == 401

def test_limit_validation_schema():
    operation = app.openapi()["paths"]["/api/v1/gis/parcels/geojson"]["get"]
    limit = next(p for p in operation["parameters"] if p["name"] == "limit")
    assert limit["schema"]["minimum"] == 1
    assert limit["schema"]["maximum"] == 500
    assert limit["schema"]["default"] == 100

class _Rows:
    def mappings(self): return []

class _CaptureDb:
    def __init__(self): self.parameters = None
    def execute(self, _query, parameters): self.parameters = parameters; return _Rows()

def test_farmer_map_query_is_scoped_to_authenticated_owner():
    farmer_db = _CaptureDb()
    parcel_features(78, 17, 79, 18, 100, None, None, Principal(subject='farmer-1', role=Role.farmer), farmer_db)
    assert farmer_db.parameters['farmer_id'] == 'farmer-1'
    officer_db = _CaptureDb()
    parcel_features(78, 17, 79, 18, 100, None, None, Principal(subject='officer-1', role=Role.officer), officer_db)
    assert officer_db.parameters['farmer_id'] is None
