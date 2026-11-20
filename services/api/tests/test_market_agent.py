import json
from datetime import date, timedelta

import pytest
from pydantic import ValidationError

from app.market_agent import (
    MarketDataError,
    MarketRequest,
    generate_market_intelligence,
    validate_market_record,
)


def sample_record(**overrides):
    values = {
        "commodity": "rice",
        "state": "Telangana",
        "district": "Hyderabad",
        "market": "Test Market",
        "price_date": date.today().isoformat(),
        "min_price_inr_per_quintal": 1800,
        "max_price_inr_per_quintal": 2200,
        "modal_price_inr_per_quintal": 2000,
        "source_name": "Test source",
        "source_url": "https://example.org/prices",
    }
    values.update(overrides)
    return values


def test_no_configured_source(monkeypatch):
    monkeypatch.delenv(
        "AGRINEXA_MARKET_SNAPSHOT_PATH",
        raising=False,
    )

    result = generate_market_intelligence(
        MarketRequest(commodity="rice")
    )

    assert result.available is False
    assert result.records == []
    assert result.source_status == "not_configured"


def test_valid_record():
    result = validate_market_record(sample_record())
    assert result.modal_price_inr_per_quintal == 2000
    assert result.freshness == "current"


def test_inconsistent_prices_rejected():
    with pytest.raises(MarketDataError):
        validate_market_record(
            sample_record(
                min_price_inr_per_quintal=2500
            )
        )


def test_future_price_date_rejected():
    tomorrow = (
        date.today() + timedelta(days=1)
    ).isoformat()

    with pytest.raises(MarketDataError):
        validate_market_record(
            sample_record(price_date=tomorrow)
        )


def test_negative_price_rejected():
    with pytest.raises(MarketDataError):
        validate_market_record(
            sample_record(
                modal_price_inr_per_quintal=-1
            )
        )


def test_stale_price_identified():
    old = (
        date.today() - timedelta(days=30)
    ).isoformat()

    result = validate_market_record(
        sample_record(price_date=old)
    )

    assert result.freshness == "stale"


def test_invalid_source_url_rejected():
    with pytest.raises(MarketDataError):
        validate_market_record(
            sample_record(
                source_url="http://example.org"
            )
        )


def test_unsupported_commodity_rejected():
    with pytest.raises(ValidationError):
        MarketRequest(commodity="unknown")


def test_extra_request_fields_rejected():
    with pytest.raises(ValidationError):
        MarketRequest(
            commodity="rice",
            password="unexpected",
        )


def test_snapshot_filtering(tmp_path, monkeypatch):
    path = tmp_path / "market.json"

    path.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "records": [
                    sample_record(),
                    sample_record(
                        commodity="maize",
                        market="Other Market",
                    ),
                ],
            }
        )
    )

    monkeypatch.setenv(
        "AGRINEXA_MARKET_SNAPSHOT_PATH",
        str(path),
    )

    result = generate_market_intelligence(
        MarketRequest(
            commodity="rice",
            state="telangana",
        )
    )

    assert result.available is True
    assert result.record_count == 1
    assert result.records[0].commodity == "rice"


def test_invalid_snapshot_fails_closed(
    tmp_path,
    monkeypatch,
):
    path = tmp_path / "market.json"
    path.write_text("{invalid-json")

    monkeypatch.setenv(
        "AGRINEXA_MARKET_SNAPSHOT_PATH",
        str(path),
    )

    with pytest.raises(MarketDataError):
        generate_market_intelligence(
            MarketRequest(commodity="rice")
        )


def test_relative_snapshot_path_rejected(monkeypatch):
    monkeypatch.setenv(
        "AGRINEXA_MARKET_SNAPSHOT_PATH",
        "relative.json",
    )

    with pytest.raises(MarketDataError):
        generate_market_intelligence(
            MarketRequest(commodity="rice")
        )


def test_version_two_snapshot_requires_and_returns_provenance(tmp_path, monkeypatch):
    from datetime import datetime, timezone
    from app.dataset_governance import canonical_dataset_hash

    now = datetime.now(timezone.utc)
    record = sample_record(
        market_id="market-001",
        observed_at=now.isoformat(),
    )
    approved = tmp_path / "approved"
    approved.mkdir()
    path = approved / "market-v2.json"
    payload = {
        "schema_version": 2,
        "snapshot_id": "approved-snapshot-001",
        "published_at": now.isoformat(),
        "source_name": "Authoritative market publisher",
        "source_url": "https://example.gov.in/market-data",
        "records": [record],
    }
    payload["governance"] = {
        "status": "approved",
        "dataset_kind": "market",
        "dataset_version": "test-v2",
        "imported_at": now.isoformat(),
        "approved_at": now.isoformat(),
        "approved_by": "test-approver",
        "source_license": "technical-test-only",
        "original_units": {"price": "INR/quintal"},
        "content_sha256": canonical_dataset_hash(payload),
    }
    path.write_text(json.dumps(payload))
    monkeypatch.setenv("AGRINEXA_MARKET_SNAPSHOT_PATH", str(path))

    result = generate_market_intelligence(MarketRequest(commodity="rice"))

    assert result.source_status == "configured_snapshot_v2"
    assert result.snapshot_id == "approved-snapshot-001"
    assert result.snapshot_version == 2
    assert result.dataset_version == "test-v2"
    assert result.imported_at is not None
    assert result.approved_at is not None
    assert result.records[0].market_id == "market-001"
    assert result.records[0].observed_at.tzinfo is not None


def test_version_two_snapshot_rejects_missing_provenance(tmp_path, monkeypatch):
    path = tmp_path / "market-v2.json"
    path.write_text(json.dumps({"schema_version": 2, "records": []}))
    monkeypatch.setenv("AGRINEXA_MARKET_SNAPSHOT_PATH", str(path))
    with pytest.raises(MarketDataError):
        generate_market_intelligence(MarketRequest(commodity="rice"))
