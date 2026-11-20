from datetime import datetime, timedelta, timezone

import pytest

from app.agent_dataset_ingestion import DatasetIngestionError
from app.market_source_data_gov import RESOURCE_ID, map_data_gov_response


RETRIEVED = datetime.now(timezone.utc) - timedelta(minutes=1)


def response(record=None):
    return {
        "index_name": RESOURCE_ID,
        "status": "ok",
        "updated_date": "2026-11-20T08:00:00Z",
        "records": [record or {
            "state": "Telangana", "district": "Hyderabad",
            "market": "Official Test Mapping Market", "commodity": "Rice",
            "variety": "Common", "grade": "FAQ", "arrival_date": "20/11/2026",
            "min_price": "1000", "max_price": "1200", "modal_price": "1100",
        }],
    }


def test_maps_official_contract_without_approving():
    mapped = map_data_gov_response(response(), retrieved_at=RETRIEVED)
    item = mapped["records"][0]
    assert mapped["schema_version"] == 2
    assert mapped["source_resource_id"] == RESOURCE_ID
    assert "governance" not in mapped
    assert item["commodity"] == "rice"
    assert item["source_commodity"] == "Rice"
    assert item["original_price_unit"] == "INR/quintal"
    assert item["observation_time_precision"] == "date"
    assert item["modal_price_inr_per_quintal"] == 1100


@pytest.mark.parametrize("change", [
    {"commodity": "Unsupported crop"},
    {"arrival_date": "not-a-date"},
    {"modal_price": "1300"},
])
def test_rejects_unsupported_or_malformed_official_records(change):
    item = response()["records"][0] | change
    with pytest.raises(DatasetIngestionError):
        map_data_gov_response(response(item), retrieved_at=RETRIEVED)


def test_rejects_duplicate_official_observations():
    payload = response()
    payload["records"].append(dict(payload["records"][0]))
    with pytest.raises(DatasetIngestionError, match="Duplicate"):
        map_data_gov_response(payload, retrieved_at=RETRIEVED)
