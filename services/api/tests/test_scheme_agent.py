import json
from datetime import date, timedelta

import pytest
from pydantic import ValidationError

from app.scheme_agent import (
    SchemeDataError,
    SchemeRequest,
    evaluate_scheme,
    generate_scheme_guidance,
    validate_record,
)

def sample(**updates):
    data = {
        "scheme_id": "test-scheme",
        "scheme_name": "Test Scheme",
        "government_level": "state",
        "states": ["Telangana"],
        "districts": [],
        "farmer_categories": ["small"],
        "minimum_land_hectares": 0,
        "maximum_land_hectares": 2,
        "documents_required": ["Identity document"],
        "application_guidance": "Check the official application portal.",
        "official_source_url": "https://example.gov.in/scheme",
        "source_verified_on": date.today().isoformat(),
        "eligibility_rules_verified": True,
    }
    data.update(updates)
    return data

def test_no_catalogue(monkeypatch):
    monkeypatch.delenv("AGRINEXA_SCHEME_CATALOGUE_PATH", raising=False)
    result = generate_scheme_guidance(SchemeRequest())
    assert result.available is False
    assert result.schemes == []
    assert result.official_approval is False

def test_valid_scheme():
    assert validate_record(sample())["scheme_id"] == "test-scheme"

def test_matching_scheme():
    record = validate_record(sample())
    status, reasons = evaluate_scheme(
        record,
        SchemeRequest(
            state="Telangana",
            farmer_category="small",
            land_area_hectares=1,
        ),
    )
    assert status == "potential_match"
    assert reasons

def test_state_mismatch():
    status, _ = evaluate_scheme(
        validate_record(sample()),
        SchemeRequest(
            state="Andhra Pradesh",
            farmer_category="small",
            land_area_hectares=1,
        ),
    )
    assert status == "not_matched"

def test_missing_details_needs_review():
    status, _ = evaluate_scheme(
        validate_record(sample()), SchemeRequest()
    )
    assert status == "needs_review"

def test_unverified_rules_needs_review():
    status, _ = evaluate_scheme(
        validate_record(sample(eligibility_rules_verified=False)),
        SchemeRequest(
            state="Telangana",
            farmer_category="small",
            land_area_hectares=1,
        ),
    )
    assert status == "needs_review"

def test_future_verification_rejected():
    tomorrow = (date.today() + timedelta(days=1)).isoformat()
    with pytest.raises(SchemeDataError):
        validate_record(sample(source_verified_on=tomorrow))

def test_insecure_url_rejected():
    with pytest.raises(SchemeDataError):
        validate_record(
            sample(official_source_url="http://example.gov.in/scheme")
        )

def test_land_range_rejected():
    with pytest.raises(SchemeDataError):
        validate_record(
            sample(minimum_land_hectares=5, maximum_land_hectares=2)
        )

def test_district_requires_state():
    with pytest.raises(ValidationError):
        SchemeRequest(district="Hyderabad")

def test_extra_fields_rejected():
    with pytest.raises(ValidationError):
        SchemeRequest(secret="unexpected")

def test_catalogue_loading(tmp_path, monkeypatch):
    path = tmp_path / "schemes.json"
    path.write_text(json.dumps({
        "schema_version": 1,
        "schemes": [sample()],
    }))
    monkeypatch.setenv("AGRINEXA_SCHEME_CATALOGUE_PATH", str(path))
    result = generate_scheme_guidance(
        SchemeRequest(
            state="Telangana",
            farmer_category="small",
            land_area_hectares=1,
        )
    )
    assert result.available is True
    assert result.schemes[0].eligibility_status == "potential_match"
    assert result.persisted is False

def test_invalid_catalogue_fails_closed(tmp_path, monkeypatch):
    path = tmp_path / "schemes.json"
    path.write_text("{broken")
    monkeypatch.setenv("AGRINEXA_SCHEME_CATALOGUE_PATH", str(path))
    with pytest.raises(SchemeDataError):
        generate_scheme_guidance(SchemeRequest())

def test_duplicate_scheme_ids_rejected(tmp_path, monkeypatch):
    path = tmp_path / "schemes.json"
    path.write_text(json.dumps({
        "schema_version": 1,
        "schemes": [sample(), sample()],
    }))
    monkeypatch.setenv("AGRINEXA_SCHEME_CATALOGUE_PATH", str(path))
    with pytest.raises(SchemeDataError):
        generate_scheme_guidance(SchemeRequest())

def test_relative_path_rejected(monkeypatch):
    monkeypatch.setenv(
        "AGRINEXA_SCHEME_CATALOGUE_PATH", "schemes.json"
    )
    with pytest.raises(SchemeDataError):
        generate_scheme_guidance(SchemeRequest())


def test_version_two_catalogue_provenance_and_effective_dates(tmp_path, monkeypatch):
    from datetime import datetime, timezone
    from app.dataset_governance import canonical_dataset_hash

    today = date.today()
    approved = tmp_path / "approved"
    approved.mkdir()
    path = approved / "schemes-v2.json"
    now = datetime.now(timezone.utc)
    payload = {
        "schema_version": 2,
        "catalogue_id": "approved-catalogue-001",
        "published_at": now.isoformat(),
        "authority_name": "Authoritative government publisher",
        "authority_source_url": "https://example.gov.in/schemes",
        "schemes": [sample(
            effective_from=(today - timedelta(days=1)).isoformat(),
            effective_until=(today + timedelta(days=30)).isoformat(),
        )],
    }
    payload["governance"] = {
        "status": "approved",
        "dataset_kind": "scheme",
        "dataset_version": "test-v2",
        "imported_at": now.isoformat(),
        "approved_at": now.isoformat(),
        "approved_by": "test-approver",
        "source_license": "technical-test-only",
        "original_units": {},
        "content_sha256": canonical_dataset_hash(payload),
    }
    path.write_text(json.dumps(payload))
    monkeypatch.setenv("AGRINEXA_SCHEME_CATALOGUE_PATH", str(path))

    result = generate_scheme_guidance(SchemeRequest(
        state="Telangana",
        farmer_category="small",
        land_area_hectares=1,
    ))

    assert result.source_status == "configured_catalogue_v2"
    assert result.catalogue_id == "approved-catalogue-001"
    assert result.catalogue_version == 2
    assert result.dataset_version == "test-v2"
    assert result.imported_at is not None
    assert result.approved_at is not None
    assert result.schemes[0].effective_until is not None


def test_expired_version_two_scheme_is_not_matched():
    yesterday = date.today() - timedelta(days=1)
    record = validate_record(
        sample(
            effective_from=(yesterday - timedelta(days=10)).isoformat(),
            effective_until=yesterday.isoformat(),
        ),
        schema_version=2,
    )
    status, reasons = evaluate_scheme(record, SchemeRequest(
        state="Telangana",
        farmer_category="small",
        land_area_hectares=1,
    ))
    assert status == "not_matched"
    assert "Scheme effective period has ended" in reasons
