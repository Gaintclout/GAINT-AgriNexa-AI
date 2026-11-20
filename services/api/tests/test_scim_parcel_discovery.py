"""Offline tests for the real-catalog discovery orchestration (no network)."""
import json
from datetime import datetime, timezone
from pathlib import Path
import pytest
from app.scim_discovery import CatalogResults, DiscoveredScene
from app.scim_parcel_discovery import discover_parcel

FIXTURE = Path(__file__).parent / "fixtures" / "scim_siddipet_sample_parcel.geojson"

def test_discovery_queries_each_provider_without_downloading():
    calls = []
    def fake_discover(search):
        calls.append(search)
        return CatalogResults(scenes=[], returned=0, truncated=False)
    report = discover_parcel(
        json.loads(FIXTURE.read_text()),
        datetime(2026, 1, 1, tzinfo=timezone.utc),
        datetime(2026, 2, 1, tzinfo=timezone.utc),
        discover=fake_discover)
    assert [c.provider.value for c in calls] == ["sentinel-2", "landsat-8", "landsat-9"]
    assert report["status"] == "catalog_metadata_only"
    assert report["real_scene_validation_complete"] is False
    assert report["providers"]["sentinel-2"]["returned"] == 0
    assert calls[0].west == 78.8595274

def test_invalid_parcel_fails_before_network():
    def unexpected(_):
        raise AssertionError("network must not be reached")
    with pytest.raises(ValueError):
        discover_parcel({"type": "Point", "coordinates": [78.86, 18.12]},
            datetime(2026, 1, 1, tzinfo=timezone.utc),
            datetime(2026, 2, 1, tzinfo=timezone.utc), discover=unexpected)

def test_invalid_cloud_limit_fails_before_network():
    def unexpected(_):
        raise AssertionError("network must not be reached")
    with pytest.raises(ValueError):
        discover_parcel(json.loads(FIXTURE.read_text()),
            datetime(2026, 1, 1, tzinfo=timezone.utc),
            datetime(2026, 2, 1, tzinfo=timezone.utc),
            max_cloud_percent=-1, discover=unexpected)
