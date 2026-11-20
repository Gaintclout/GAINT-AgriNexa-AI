from datetime import datetime, timedelta, timezone
import pytest
from pydantic import ValidationError
from app.scim_contracts import SceneCandidate, assess_scene
from app.main import app

def candidate(**overrides):
    values = dict(provider="sentinel-2", scene_id="S2_20261001_A",
                  captured_at=datetime(2026, 10, 1, tzinfo=timezone.utc),
                  cloud_cover_percent=12.5, west=78.0, south=17.0, east=79.0, north=18.0)
    values.update(overrides)
    return SceneCandidate(**values)

def test_usable_scene():
    result = assess_scene(candidate(), 30)
    assert result.usable is True
    assert result.reasons == []

def test_cloudy_scene_rejected():
    result = assess_scene(candidate(cloud_cover_percent=70), 30)
    assert result.usable is False
    assert result.reasons

@pytest.mark.parametrize("changes", [
    {"west": 80.0}, {"north": 16.0}, {"cloud_cover_percent": 101},
    {"scene_id": "../bad"}, {"captured_at": datetime(2026, 10, 1)},
    {"captured_at": datetime.now(timezone.utc) + timedelta(days=2)},
])
def test_invalid_scene_metadata(changes):
    with pytest.raises(ValidationError):
        candidate(**changes)

def test_scim_endpoint_documented():
    operation = app.openapi()["paths"]["/api/v1/scim/scenes/assess"]["post"]
    assert operation["tags"] == ["scim"]
