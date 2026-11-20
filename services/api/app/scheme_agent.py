"""Read-only, source-backed government scheme discovery.

No scheme data is fabricated. A locally verified catalogue must
be explicitly configured before any scheme can be returned.
"""

from __future__ import annotations

import json
import math
import os
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Literal
from urllib.parse import urlparse

from pydantic import BaseModel, ConfigDict, Field, model_validator

from .dataset_governance import (
    DatasetGovernanceError,
    validate_approved_governance,
)

MAX_BYTES = 2_000_000
MAX_SCHEMES = 500
MAX_TEXT = 2000

class SchemeDataError(Exception):
    pass

def text_value(value, maximum=200):
    if not isinstance(value, str):
        raise SchemeDataError("Invalid scheme text")
    value = value.strip()
    if not value or len(value) > maximum:
        raise SchemeDataError("Invalid scheme text")
    return value

def https_url(value):
    value = text_value(value, 1000)
    parsed = urlparse(value)
    if (
        parsed.scheme != "https"
        or not parsed.hostname
        or parsed.username
        or parsed.password
        or parsed.fragment
        or parsed.port is not None
        or parsed.hostname in ("localhost", "127.0.0.1")
    ):
        raise SchemeDataError("Invalid official source URL")
    return value

class SchemeRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    state: str | None = Field(default=None, max_length=100)
    district: str | None = Field(default=None, max_length=100)
    farmer_category: Literal[
        "small", "marginal", "other"
    ] | None = None
    land_area_hectares: float | None = Field(
        default=None, ge=0, le=100000
    )
    limit: int = Field(default=20, ge=1, le=50)

    @model_validator(mode="after")
    def validate_location(self):
        if self.district and not self.state:
            raise ValueError("State is required when district is supplied")
        return self

class SchemeRecord(BaseModel):
    scheme_id: str
    scheme_name: str
    government_level: str
    states: list[str]
    districts: list[str]
    farmer_categories: list[str]
    minimum_land_hectares: float | None
    maximum_land_hectares: float | None
    documents_required: list[str]
    application_guidance: str
    official_source_url: str
    source_verified_on: date
    effective_from: date | None = None
    effective_until: date | None = None
    eligibility_rules_verified: bool
    eligibility_status: str
    eligibility_reasons: list[str]
    source_age_days: int

class SchemeResult(BaseModel):
    schemes: list[SchemeRecord]
    record_count: int
    available: bool
    source_status: str
    message: str
    catalogue_id: str | None = None
    catalogue_version: int | None = None
    dataset_version: str | None = None
    imported_at: datetime | None = None
    approved_at: datetime | None = None
    published_at: datetime | None = None
    authority_name: str | None = None
    authority_source_url: str | None = None
    advisory_only: bool = True
    official_approval: bool = False
    persisted: bool = False

def _date_value(value, label):
    try:
        return date.fromisoformat(text_value(value, 10))
    except ValueError as exc:
        raise SchemeDataError(f"Invalid {label} date") from exc


def _timestamp(value, label):
    try:
        parsed = datetime.fromisoformat(
            text_value(value, 40).replace("Z", "+00:00")
        )
    except ValueError as exc:
        raise SchemeDataError(f"Invalid {label} timestamp") from exc
    if parsed.tzinfo is None or parsed > datetime.now(timezone.utc):
        raise SchemeDataError(f"Invalid {label} timestamp")
    return parsed


def validate_record(raw, today=None, *, schema_version=1):
    if not isinstance(raw, dict):
        raise SchemeDataError("Invalid scheme record")

    today = today or datetime.now(timezone.utc).date()
    required = {
        "scheme_id", "scheme_name", "government_level",
        "states", "districts", "farmer_categories",
        "documents_required", "application_guidance",
        "official_source_url", "source_verified_on",
        "eligibility_rules_verified",
    }
    if not required.issubset(raw):
        raise SchemeDataError("Missing required scheme fields")

    def string_list(key, maximum=100):
        values = raw[key]
        if not isinstance(values, list) or len(values) > maximum:
            raise SchemeDataError("Invalid scheme list")
        result = [text_value(value) for value in values]
        if len({v.casefold() for v in result}) != len(result):
            raise SchemeDataError("Duplicate scheme list values")
        return result

    level = text_value(raw["government_level"], 40).lower()
    if level not in ("central", "state"):
        raise SchemeDataError("Invalid government level")

    states = string_list("states")
    districts = string_list("districts")
    categories = string_list("farmer_categories")

    if any(v not in ("small", "marginal", "other") for v in categories):
        raise SchemeDataError("Invalid farmer category")

    if districts and not states:
        raise SchemeDataError("Districts require states")

    def land_value(key):
        value = raw.get(key)
        if value is None:
            return None
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise SchemeDataError("Invalid land requirement")
        value = float(value)
        if not math.isfinite(value) or not 0 <= value <= 100000:
            raise SchemeDataError("Invalid land requirement")
        return value

    minimum = land_value("minimum_land_hectares")
    maximum = land_value("maximum_land_hectares")
    if minimum is not None and maximum is not None and minimum > maximum:
        raise SchemeDataError("Invalid land range")

    verified = raw["eligibility_rules_verified"]
    if not isinstance(verified, bool):
        raise SchemeDataError("Invalid verification flag")

    try:
        verified_on = date.fromisoformat(
            text_value(raw["source_verified_on"], 10)
        )
    except ValueError as exc:
        raise SchemeDataError("Invalid verification date") from exc

    if verified_on > today:
        raise SchemeDataError("Future verification date")

    effective_from = None
    effective_until = None
    if schema_version == 2:
        effective_from = _date_value(raw.get("effective_from"), "effective from")
        if raw.get("effective_until") is not None:
            effective_until = _date_value(
                raw.get("effective_until"), "effective until"
            )
        if effective_until is not None and effective_until < effective_from:
            raise SchemeDataError("Invalid effective date range")

    return {
        "scheme_id": text_value(raw["scheme_id"], 100),
        "scheme_name": text_value(raw["scheme_name"]),
        "government_level": level,
        "states": states,
        "districts": districts,
        "farmer_categories": categories,
        "minimum_land_hectares": minimum,
        "maximum_land_hectares": maximum,
        "documents_required": string_list("documents_required"),
        "application_guidance": text_value(
            raw["application_guidance"], MAX_TEXT
        ),
        "official_source_url": https_url(raw["official_source_url"]),
        "source_verified_on": verified_on,
        "effective_from": effective_from,
        "effective_until": effective_until,
        "eligibility_rules_verified": verified,
    }

def load_catalogue():
    configured = os.environ.get(
        "AGRINEXA_SCHEME_CATALOGUE_PATH", ""
    ).strip()
    if not configured:
        return [], "not_configured", None

    path = Path(configured)
    if not path.is_absolute():
        raise SchemeDataError("Catalogue path must be absolute")

    try:
        if not path.is_file() or path.stat().st_size > MAX_BYTES:
            raise SchemeDataError("Catalogue unavailable or oversized")
        with path.open("rb") as stream:
            data = stream.read(MAX_BYTES + 1)
        if len(data) > MAX_BYTES:
            raise SchemeDataError("Catalogue oversized")
        payload = json.loads(data)
    except (OSError, ValueError, UnicodeError) as exc:
        raise SchemeDataError("Catalogue cannot be loaded") from exc

    if not isinstance(payload, dict):
        raise SchemeDataError("Unsupported catalogue schema")
    schema_version = payload.get("schema_version")
    if schema_version not in (1, 2):
        raise SchemeDataError("Unsupported catalogue schema")

    records = payload.get("schemes")
    if not isinstance(records, list) or len(records) > MAX_SCHEMES:
        raise SchemeDataError("Invalid catalogue records")

    metadata = None
    if schema_version == 2:
        try:
            governance = validate_approved_governance(
                payload,
                dataset_kind="scheme",
            )
        except DatasetGovernanceError as exc:
            raise SchemeDataError(str(exc)) from exc
        if path.parent.name != "approved":
            raise SchemeDataError("Version-2 scheme dataset is not in approved storage")
        metadata = {
            "catalogue_id": text_value(payload.get("catalogue_id"), 100),
            "catalogue_version": 2,
            "dataset_version": governance["dataset_version"],
            "imported_at": governance["imported_at"],
            "approved_at": governance["approved_at"],
            "published_at": _timestamp(
                payload.get("published_at"), "publication"
            ),
            "authority_name": text_value(
                payload.get("authority_name"), 200
            ),
            "authority_source_url": https_url(
                payload.get("authority_source_url")
            ),
        }

    validated = [
        validate_record(record, schema_version=schema_version)
        for record in records
    ]
    ids = [record["scheme_id"].casefold() for record in validated]
    if len(set(ids)) != len(ids):
        raise SchemeDataError("Duplicate scheme identifiers")

    return validated, (
        "configured_catalogue_v2" if schema_version == 2
        else "configured_catalogue_v1"
    ), metadata

def evaluate_scheme(record, request):
    reasons = []
    unknown = []
    today = datetime.now(timezone.utc).date()

    if record.get("effective_from") and today < record["effective_from"]:
        reasons.append("Scheme is not yet effective")
    if record.get("effective_until") and today > record["effective_until"]:
        reasons.append("Scheme effective period has ended")

    if record["states"]:
        if not request.state:
            unknown.append("State not provided")
        elif request.state.casefold() not in {
            value.casefold() for value in record["states"]
        }:
            reasons.append("State outside published scope")

    if record["districts"]:
        if not request.district:
            unknown.append("District not provided")
        elif request.district.casefold() not in {
            value.casefold() for value in record["districts"]
        }:
            reasons.append("District outside published scope")

    if record["farmer_categories"]:
        if not request.farmer_category:
            unknown.append("Farmer category not provided")
        elif request.farmer_category not in record["farmer_categories"]:
            reasons.append("Farmer category outside stated requirements")

    if (
        record["minimum_land_hectares"] is not None
        or record["maximum_land_hectares"] is not None
    ):
        area = request.land_area_hectares
        if area is None:
            unknown.append("Land area not provided")
        elif (
            record["minimum_land_hectares"] is not None
            and area < record["minimum_land_hectares"]
        ) or (
            record["maximum_land_hectares"] is not None
            and area > record["maximum_land_hectares"]
        ):
            reasons.append("Land area outside stated requirements")

    if not record["eligibility_rules_verified"]:
        unknown.append("Eligibility rules not independently verified")

    if reasons:
        return "not_matched", reasons
    if unknown:
        return "needs_review", unknown

    return "potential_match", [
        "Supplied attributes match the configured screening rules; "
        "official eligibility has not been determined"
    ]

def generate_scheme_guidance(request: SchemeRequest):
    records, status, metadata = load_catalogue()
    today = datetime.now(timezone.utc).date()

    results = []
    for record in records:
        eligibility, reasons = evaluate_scheme(record, request)
        results.append(SchemeRecord(
            **record,
            eligibility_status=eligibility,
            eligibility_reasons=reasons,
            source_age_days=(today - record["source_verified_on"]).days,
        ))

    priority = {
        "potential_match": 0,
        "needs_review": 1,
        "not_matched": 2,
    }
    results.sort(
        key=lambda item: (
            priority[item.eligibility_status],
            item.scheme_name.casefold(),
        )
    )
    total = len(results)
    results = results[:request.limit]

    if status == "not_configured":
        message = (
            "No verified government scheme catalogue is configured. "
            "No scheme or eligibility information has been invented."
        )
    elif not results:
        message = "No schemes are available in the configured catalogue."
    else:
        message = (
            "Preliminary screening only. Verify current eligibility, "
            "benefits and application procedures on the official website."
        )

    return SchemeResult(
        schemes=results,
        record_count=total,
        available=bool(results),
        source_status=status,
        message=message,
        **(metadata or {}),
    )
