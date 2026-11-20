import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient
from app.boundary import normalize_boundary
from app.main import app

RING = [[78.1, 17.1], [78.2, 17.1], [78.2, 17.2], [78.1, 17.1]]

def test_polygon_normalizes_to_multipolygon():
    result = normalize_boundary({"type": "Polygon", "coordinates": [RING]})
    assert result == {"type": "MultiPolygon", "coordinates": [[RING]]}

def test_multipolygon_is_accepted():
    result = normalize_boundary({"type": "MultiPolygon", "coordinates": [[RING]]})
    assert result["type"] == "MultiPolygon"

@pytest.mark.parametrize("boundary", [
    {"type": "Point", "coordinates": [78, 17]},
    {"type": "Polygon", "coordinates": []},
    {"type": "Polygon", "coordinates": [[[78,17],[79,17],[79,18],[78,18]]]},
    {"type": "Polygon", "coordinates": [[[181,17],[79,17],[79,18],[181,17]]]},
    {"type": "Polygon", "coordinates": [[[78,17],[79,17],[79,18]]]},
])
def test_rejects_invalid_boundaries(boundary):
    with pytest.raises(HTTPException) as exc:
        normalize_boundary(boundary)
    assert exc.value.status_code == 422

def test_boundary_endpoints_require_auth():
    client = TestClient(app)
    assert client.get("/api/v1/parcels/unknown/boundary").status_code == 401
    assert client.put("/api/v1/parcels/unknown/boundary", json={"geometry": {"type": "Polygon", "coordinates": [RING]}}).status_code == 401
