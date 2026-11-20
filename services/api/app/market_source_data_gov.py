"""Offline adapter for the official data.gov.in AGMARKNET resource.

This module never performs network access and never approves a dataset.  It maps a
previously retrieved, immutable JSON response into the governed v2 input contract.
"""

from __future__ import annotations

from datetime import datetime, time, timezone
from hashlib import sha256
from typing import Any

from .agent_dataset_ingestion import DatasetIngestionError


RESOURCE_ID = "9ef84268-d588-465a-a308-a864a43d0070"
RESOURCE_URL = (
    "https://www.data.gov.in/resource/"
    "current-daily-price-various-commodities-various-markets-mandi"
)
PRICE_UNIT = "INR/quintal"
SUPPORTED_COMMODITIES = {
    "rice": "rice",
    "paddy(dhan)(common)": "rice",
    "wheat": "wheat",
    "maize": "maize",
    "cotton": "cotton",
    "ground nut seed": "groundnut",
    "groundnut": "groundnut",
    "tomato": "tomato",
}


def _text(record: dict[str, Any], key: str, maximum: int = 200) -> str:
    value = record.get(key)
    if not isinstance(value, str) or not value.strip() or len(value.strip()) > maximum:
        raise DatasetIngestionError(f"Invalid official market field: {key}")
    return value.strip()


def _price(record: dict[str, Any], key: str) -> float:
    value = record.get(key)
    if isinstance(value, bool):
        raise DatasetIngestionError(f"Invalid official market field: {key}")
    try:
        number = float(value)
    except (TypeError, ValueError, OverflowError) as exc:
        raise DatasetIngestionError(f"Invalid official market field: {key}") from exc
    if not 0 <= number <= 10_000_000:
        raise DatasetIngestionError(f"Invalid official market field: {key}")
    return number


def _arrival_date(value: str):
    for pattern in ("%d/%m/%Y", "%Y-%m-%d"):
        try:
            return datetime.strptime(value, pattern).date()
        except ValueError:
            pass
    raise DatasetIngestionError("Invalid official market field: arrival_date")


def map_data_gov_response(payload: dict, *, retrieved_at: datetime) -> dict:
    """Map one captured API response; unsupported records fail the entire import."""
    if retrieved_at.tzinfo is None or retrieved_at > datetime.now(timezone.utc):
        raise DatasetIngestionError("Retrieval timestamp must be timezone-aware and not future")
    if not isinstance(payload, dict) or payload.get("index_name") != RESOURCE_ID:
        raise DatasetIngestionError("Unexpected data.gov.in resource identity")
    if payload.get("status") != "ok":
        raise DatasetIngestionError("Official market response status is not ok")
    records = payload.get("records")
    if not isinstance(records, list) or not records:
        raise DatasetIngestionError("Official market response has no records")

    mapped = []
    seen = set()
    for source in records:
        if not isinstance(source, dict):
            raise DatasetIngestionError("Invalid official market record")
        original_commodity = _text(source, "commodity", 100)
        commodity = SUPPORTED_COMMODITIES.get(original_commodity.casefold())
        if commodity is None:
            raise DatasetIngestionError(
                f"Unsupported official commodity: {original_commodity}"
            )
        state = _text(source, "state")
        district = _text(source, "district")
        market = _text(source, "market")
        variety = _text(source, "variety")
        grade = _text(source, "grade")
        observed_date = _arrival_date(_text(source, "arrival_date", 10))
        observed_at = datetime.combine(observed_date, time.min, timezone.utc)
        minimum = _price(source, "min_price")
        maximum = _price(source, "max_price")
        modal = _price(source, "modal_price")
        if not minimum <= modal <= maximum:
            raise DatasetIngestionError("Inconsistent official market price range")
        market_id = "DGV-" + sha256(
            "|".join((state, district, market)).casefold().encode("utf-8")
        ).hexdigest()[:20]
        identity = tuple(
            value.casefold() if isinstance(value, str) else value
            for value in (market_id, commodity, variety, grade, observed_date.isoformat())
        )
        if identity in seen:
            raise DatasetIngestionError("Duplicate official market observation")
        seen.add(identity)
        mapped.append({
            "market_id": market_id,
            "commodity": commodity,
            "source_commodity": original_commodity,
            "variety": variety,
            "grade": grade,
            "state": state,
            "district": district,
            "market": market,
            "price_date": observed_date.isoformat(),
            # The source supplies date precision only. Midnight is a deterministic
            # serialization, explicitly labelled below, not a claimed event time.
            "observed_at": observed_at.isoformat(),
            "observation_time_precision": "date",
            "min_price_inr_per_quintal": minimum,
            "max_price_inr_per_quintal": maximum,
            "modal_price_inr_per_quintal": modal,
            "original_price_unit": PRICE_UNIT,
            "source_name": "OGD Platform India / AGMARKNET",
            "source_url": RESOURCE_URL,
        })

    response_updated = payload.get("updated_date")
    if not isinstance(response_updated, str) or not response_updated.strip():
        raise DatasetIngestionError("Official response publication timestamp missing")
    return {
        "schema_version": 2,
        "snapshot_id": f"DATA-GOV-IN-{RESOURCE_ID}-{retrieved_at:%Y%m%dT%H%M%SZ}",
        "published_at": response_updated,
        "retrieved_at": retrieved_at.isoformat(),
        "source_name": "OGD Platform India / AGMARKNET",
        "source_url": RESOURCE_URL,
        "source_resource_id": RESOURCE_ID,
        "records": mapped,
    }
