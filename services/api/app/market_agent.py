"""Read-only agricultural market intelligence.

Prices are returned only from an explicitly configured,
validated local data snapshot. No synthetic market prices.
"""

from __future__ import annotations

from datetime import date, datetime, timezone
from pathlib import Path
from typing import Literal
import json
import os

from pydantic import BaseModel, ConfigDict, Field

from .dataset_governance import (
    DatasetGovernanceError,
    validate_approved_governance,
)


Commodity = Literal[
    "rice",
    "wheat",
    "maize",
    "cotton",
    "groundnut",
    "tomato",
]

MAX_SNAPSHOT_BYTES = 2_000_000
MAX_RECORDS = 5000


class MarketRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    commodity: Commodity
    state: str | None = Field(
        default=None,
        max_length=100,
    )
    district: str | None = Field(
        default=None,
        max_length=100,
    )
    market: str | None = Field(default=None, max_length=120)
    limit: int = Field(default=20, ge=1, le=50)


class MarketPrice(BaseModel):
    market_id: str | None = None
    commodity: str
    source_commodity: str | None = None
    variety: str | None = None
    grade: str | None = None
    state: str
    district: str
    market: str
    price_date: date
    observed_at: datetime | None = None
    observation_time_precision: str | None = None
    min_price_inr_per_quintal: float
    max_price_inr_per_quintal: float
    modal_price_inr_per_quintal: float
    source_name: str
    source_url: str | None = None
    original_price_unit: str | None = None
    age_days: int
    freshness: str


class MarketResult(BaseModel):
    commodity: Commodity
    state: str | None
    district: str | None
    records: list[MarketPrice]
    record_count: int
    available: bool
    message: str
    source_status: str
    snapshot_id: str | None = None
    snapshot_version: int | None = None
    dataset_version: str | None = None
    imported_at: datetime | None = None
    approved_at: datetime | None = None
    published_at: datetime | None = None
    snapshot_source_name: str | None = None
    snapshot_source_url: str | None = None
    advisory_only: bool = True
    persisted: bool = False
    currency: str = "INR"
    unit: str = "quintal"


class MarketDataError(Exception):
    pass


def _safe_text(value, maximum=120):
    if not isinstance(value, str):
        raise MarketDataError("Invalid market record text")

    value = value.strip()

    if not value or len(value) > maximum:
        raise MarketDataError("Invalid market record text")

    return value


def _safe_price(value):
    if isinstance(value, bool):
        raise MarketDataError("Invalid market price")

    try:
        number = float(value)
    except (TypeError, ValueError, OverflowError) as exc:
        raise MarketDataError("Invalid market price") from exc

    import math

    if not math.isfinite(number) or number < 0 or number > 10000000:
        raise MarketDataError("Invalid market price")

    return number


def _timestamp(value, label):
    try:
        parsed = datetime.fromisoformat(
            _safe_text(value, 40).replace("Z", "+00:00")
        )
    except ValueError as exc:
        raise MarketDataError(f"Invalid {label} timestamp") from exc
    if parsed.tzinfo is None or parsed > datetime.now(timezone.utc):
        raise MarketDataError(f"Invalid {label} timestamp")
    return parsed


def validate_market_record(raw, today=None, *, schema_version=1):
    if not isinstance(raw, dict):
        raise MarketDataError("Invalid market record")

    today = today or datetime.now(timezone.utc).date()

    commodity = _safe_text(raw.get("commodity"), 80).lower()

    if commodity not in (
        "rice", "wheat", "maize",
        "cotton", "groundnut", "tomato",
    ):
        raise MarketDataError("Unsupported commodity")

    try:
        price_date = date.fromisoformat(
            _safe_text(raw.get("price_date"), 10)
        )
    except ValueError as exc:
        raise MarketDataError("Invalid market date") from exc

    if price_date > today:
        raise MarketDataError("Future market price date")

    age = (today - price_date).days

    minimum = _safe_price(
        raw.get("min_price_inr_per_quintal")
    )
    maximum = _safe_price(
        raw.get("max_price_inr_per_quintal")
    )
    modal = _safe_price(
        raw.get("modal_price_inr_per_quintal")
    )

    if not minimum <= modal <= maximum:
        raise MarketDataError("Inconsistent market price range")

    source_url = raw.get("source_url")

    if source_url is not None:
        from urllib.parse import urlparse

        if (
            not isinstance(source_url, str)
            or len(source_url) > 500
        ):
            raise MarketDataError("Invalid source URL")

        parsed = urlparse(source_url)

        if (
            parsed.scheme != "https"
            or not parsed.hostname
            or parsed.username
            or parsed.password
        ):
            raise MarketDataError("Invalid source URL")

    freshness = (
        "current" if age <= 2
        else "recent" if age <= 7
        else "stale"
    )

    return MarketPrice(
        market_id=(
            _safe_text(raw.get("market_id"), 100)
            if schema_version == 2 else None
        ),
        commodity=commodity,
        source_commodity=(
            _safe_text(raw.get("source_commodity"), 100)
            if raw.get("source_commodity") is not None else None
        ),
        variety=(
            _safe_text(raw.get("variety"), 120)
            if raw.get("variety") is not None else None
        ),
        grade=(
            _safe_text(raw.get("grade"), 120)
            if raw.get("grade") is not None else None
        ),
        state=_safe_text(raw.get("state")),
        district=_safe_text(raw.get("district")),
        market=_safe_text(raw.get("market")),
        price_date=price_date,
        observed_at=(
            _timestamp(raw.get("observed_at"), "observation")
            if schema_version == 2 else None
        ),
        observation_time_precision=(
            _safe_text(raw.get("observation_time_precision"), 20)
            if raw.get("observation_time_precision") is not None else None
        ),
        min_price_inr_per_quintal=minimum,
        max_price_inr_per_quintal=maximum,
        modal_price_inr_per_quintal=modal,
        source_name=_safe_text(raw.get("source_name")),
        source_url=source_url,
        original_price_unit=(
            _safe_text(raw.get("original_price_unit"), 40)
            if raw.get("original_price_unit") is not None else None
        ),
        age_days=age,
        freshness=freshness,
    )


def load_market_snapshot():
    """Read configured snapshot without modifying any file."""

    configured = os.environ.get(
        "AGRINEXA_MARKET_SNAPSHOT_PATH",
        "",
    ).strip()

    if not configured:
        return [], "not_configured", None

    path = Path(configured)

    if not path.is_absolute():
        raise MarketDataError(
            "Market snapshot path must be absolute"
        )

    try:
        if not path.is_file():
            raise MarketDataError(
                "Market snapshot file unavailable"
            )

        if path.stat().st_size > MAX_SNAPSHOT_BYTES:
            raise MarketDataError(
                "Market snapshot exceeds size limit"
            )

        with path.open("rb") as handle:
            raw_bytes = handle.read(MAX_SNAPSHOT_BYTES + 1)

        if len(raw_bytes) > MAX_SNAPSHOT_BYTES:
            raise MarketDataError(
                "Market snapshot exceeds size limit"
            )

        payload = json.loads(raw_bytes)

    except (OSError, ValueError, UnicodeError) as exc:
        raise MarketDataError(
            "Market snapshot could not be loaded"
        ) from exc

    if not isinstance(payload, dict):
        raise MarketDataError("Invalid market snapshot")

    schema_version = payload.get("schema_version")
    if schema_version not in (1, 2):
        raise MarketDataError(
            "Unsupported market snapshot schema"
        )

    records = payload.get("records")

    if not isinstance(records, list):
        raise MarketDataError("Invalid market snapshot records")

    if len(records) > MAX_RECORDS:
        raise MarketDataError("Too many market records")

    metadata = None
    if schema_version == 2:
        try:
            governance = validate_approved_governance(
                payload,
                dataset_kind="market",
                required_unit="INR/quintal",
            )
        except DatasetGovernanceError as exc:
            raise MarketDataError(str(exc)) from exc
        if path.parent.name != "approved":
            raise MarketDataError("Version-2 market dataset is not in approved storage")
        metadata = {
            "snapshot_id": _safe_text(payload.get("snapshot_id"), 100),
            "snapshot_version": 2,
            "dataset_version": governance["dataset_version"],
            "imported_at": governance["imported_at"],
            "approved_at": governance["approved_at"],
            "published_at": _timestamp(
                payload.get("published_at"), "publication"
            ),
            "snapshot_source_name": _safe_text(
                payload.get("source_name"), 200
            ),
            "snapshot_source_url": payload.get("source_url"),
        }
        from urllib.parse import urlparse
        source_url = metadata["snapshot_source_url"]
        parsed = urlparse(source_url) if isinstance(source_url, str) else None
        if (
            not parsed
            or parsed.scheme != "https"
            or not parsed.hostname
            or parsed.username
            or parsed.password
        ):
            raise MarketDataError("Invalid snapshot source URL")

    validated = [
        validate_market_record(item, schema_version=schema_version)
        for item in records
    ]
    if schema_version == 2:
        identifiers = [(
            item.market_id.casefold(), item.commodity,
            (item.variety or "").casefold(), (item.grade or "").casefold(),
            item.price_date,
        ) for item in validated]
        if len(identifiers) != len(set(identifiers)):
            raise MarketDataError("Duplicate market identifiers")

    return validated, (
        "configured_snapshot_v2" if schema_version == 2
        else "configured_snapshot_v1"
    ), metadata


def generate_market_intelligence(request: MarketRequest):
    records, source_status, metadata = load_market_snapshot()

    state = request.state.strip() if request.state else None
    district = (
        request.district.strip() if request.district else None
    )
    market = request.market.strip() if request.market else None

    matches = [
        item
        for item in records
        if item.commodity == request.commodity
        and (
            not state
            or item.state.casefold() == state.casefold()
        )
        and (
            not district
            or item.district.casefold() == district.casefold()
        )
        and (not market or item.market.casefold() == market.casefold())
    ]

    # Most recent prices first, then consistent market ordering.
    matches.sort(
        key=lambda item: (
            -item.price_date.toordinal(),
            item.state.casefold(),
            item.district.casefold(),
            item.market.casefold(),
        )
    )

    selected = matches[:request.limit]

    if source_status == "not_configured":
        message = (
            "No verified market data source is configured. "
            "Live prices are not available."
        )
    elif not selected:
        message = (
            "No verified market price records match "
            "the selected filters."
        )
    else:
        message = (
            "Market prices are from a configured snapshot. "
            "Check the date and source of each record."
        )

    return MarketResult(
        commodity=request.commodity,
        state=state,
        district=district,
        records=selected,
        record_count=len(matches),
        available=bool(selected),
        message=message,
        source_status=source_status,
        **(metadata or {}),
    )
