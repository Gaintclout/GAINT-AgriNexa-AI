import json
from datetime import date, datetime, timedelta, timezone

import pytest

from app.agent_dataset_ingestion import (
    DatasetIngestionError,
    approve_validated,
    import_draft,
    reject_validated,
    validate_draft,
)
from app.market_agent import MarketDataError, load_market_snapshot
from app.scheme_agent import SchemeDataError, load_catalogue


NOW = datetime.now(timezone.utc)


def market_payload(**updates):
    payload = {
        "schema_version": 2,
        "snapshot_id": "SYNTHETIC-TECHNICAL-MARKET",
        "published_at": NOW.isoformat(),
        "source_name": "Synthetic technical fixture - not production data",
        "source_url": "https://example.gov.in/technical-fixture",
        "records": [{
            "market_id": "TEST-MARKET-1",
            "commodity": "rice",
            "state": "Telangana",
            "district": "Test District",
            "market": "Synthetic Test Market",
            "price_date": date.today().isoformat(),
            "observed_at": NOW.isoformat(),
            "min_price_inr_per_quintal": 100,
            "max_price_inr_per_quintal": 300,
            "modal_price_inr_per_quintal": 200,
            "source_name": "Synthetic technical fixture",
            "source_url": "https://example.gov.in/technical-fixture",
        }],
    }
    payload.update(updates)
    return payload


def scheme_payload(**updates):
    payload = {
        "schema_version": 2,
        "catalogue_id": "SYNTHETIC-TECHNICAL-SCHEMES",
        "published_at": NOW.isoformat(),
        "authority_name": "Synthetic technical fixture - not an authority",
        "authority_source_url": "https://example.gov.in/technical-fixture",
        "schemes": [{
            "scheme_id": "TEST-SCHEME-1",
            "scheme_name": "Synthetic Technical Scheme",
            "government_level": "state",
            "states": ["Telangana"],
            "districts": [],
            "farmer_categories": ["small"],
            "minimum_land_hectares": 0,
            "maximum_land_hectares": 2,
            "documents_required": ["Synthetic document"],
            "application_guidance": "Technical fixture only; do not apply.",
            "official_source_url": "https://example.gov.in/technical-fixture",
            "source_verified_on": date.today().isoformat(),
            "effective_from": (date.today() - timedelta(days=1)).isoformat(),
            "effective_until": (date.today() + timedelta(days=1)).isoformat(),
            "eligibility_rules_verified": False,
        }],
    }
    payload.update(updates)
    return payload


def write_source(tmp_path, name, payload):
    path = tmp_path / name
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


@pytest.mark.parametrize(
    ("kind", "payload", "units"),
    [
        ("market", market_payload, {"price": "INR/quintal"}),
        ("scheme", scheme_payload, {}),
    ],
)
def test_draft_validate_approve_is_deterministic(tmp_path, kind, payload, units):
    source = write_source(tmp_path, f"{kind}.json", payload())
    root = tmp_path / "governed"
    kwargs = dict(
        dataset_version="technical-fixture-v1",
        source_license="synthetic technical fixture; no production use",
        original_units=units,
        imported_at=NOW,
    )
    draft = import_draft(source, root, kind, **kwargs)
    assert import_draft(source, root, kind, **kwargs) == draft
    validated = validate_draft(draft, root, kind)
    approved = approve_validated(
        validated, root, kind,
        approved_by="technical-test-approver",
        reviewer_role="admin",
        approved_at=NOW,
    )
    content = json.loads(approved.read_text(encoding="utf-8"))
    assert content["governance"]["status"] == "approved"
    assert content["governance"]["content_sha256"]
    assert approved.parent.name == "approved"


def test_import_and_approval_timestamps_are_ordered(tmp_path):
    source = write_source(tmp_path, "market.json", market_payload())
    root = tmp_path / "governed"
    with pytest.raises(DatasetIngestionError, match="future"):
        import_draft(
            source, root, "market", dataset_version="technical-v1",
            source_license="technical fixture",
            original_units={"price": "INR/quintal"},
            imported_at=NOW + timedelta(days=1),
        )
    draft = import_draft(
        source, root, "market", dataset_version="technical-v1",
        source_license="technical fixture",
        original_units={"price": "INR/quintal"}, imported_at=NOW,
    )
    validated = validate_draft(draft, root, "market")
    with pytest.raises(DatasetIngestionError, match="predate"):
        approve_validated(
            validated, root, "market", approved_by="technical-approver",
            reviewer_role="admin",
            approved_at=NOW - timedelta(seconds=1),
        )


def test_market_loader_rejects_draft_and_accepts_approved(tmp_path, monkeypatch):
    source = write_source(tmp_path, "market.json", market_payload())
    root = tmp_path / "governed"
    draft = import_draft(
        source, root, "market",
        dataset_version="technical-v1",
        source_license="technical fixture",
        original_units={"price": "INR/quintal"},
        imported_at=NOW,
    )
    monkeypatch.setenv("AGRINEXA_MARKET_SNAPSHOT_PATH", str(draft))
    with pytest.raises(MarketDataError, match="not approved"):
        load_market_snapshot()
    approved = approve_validated(
        validate_draft(draft, root, "market"), root, "market",
        approved_by="technical-test-approver", approved_at=NOW,
        reviewer_role="admin",
    )
    monkeypatch.setenv("AGRINEXA_MARKET_SNAPSHOT_PATH", str(approved))
    records, status, metadata = load_market_snapshot()
    assert status == "configured_snapshot_v2"
    assert metadata["snapshot_id"] == "SYNTHETIC-TECHNICAL-MARKET"
    assert len(records) == 1


def test_scheme_loader_rejects_validated_but_unapproved(tmp_path, monkeypatch):
    source = write_source(tmp_path, "scheme.json", scheme_payload())
    root = tmp_path / "governed"
    validated = validate_draft(import_draft(
        source, root, "scheme",
        dataset_version="technical-v1",
        source_license="technical fixture",
        original_units={}, imported_at=NOW,
    ), root, "scheme")
    monkeypatch.setenv("AGRINEXA_SCHEME_CATALOGUE_PATH", str(validated))
    with pytest.raises(SchemeDataError, match="not approved"):
        load_catalogue()


def test_duplicate_market_identifier_rejected(tmp_path):
    payload = market_payload()
    payload["records"].append(dict(payload["records"][0]))
    source = write_source(tmp_path, "duplicates.json", payload)
    root = tmp_path / "governed"
    draft = import_draft(
        source, root, "market",
        dataset_version="technical-v1",
        source_license="technical fixture",
        original_units={"price": "INR/quintal"}, imported_at=NOW,
    )
    with pytest.raises(DatasetIngestionError, match="Duplicate market"):
        validate_draft(draft, root, "market")


def test_invalid_record_and_unsupported_unit_rejected(tmp_path):
    payload = market_payload()
    payload["records"][0].pop("observed_at")
    source = write_source(tmp_path, "invalid.json", payload)
    root = tmp_path / "governed"
    with pytest.raises(DatasetIngestionError, match="source unit"):
        import_draft(
            source, root, "market",
            dataset_version="technical-v1",
            source_license="technical fixture",
            original_units={"price": "INR/kg"}, imported_at=NOW,
        )
    draft = import_draft(
        source, root, "market",
        dataset_version="technical-v1",
        source_license="technical fixture",
        original_units={"price": "INR/quintal"}, imported_at=NOW,
    )
    with pytest.raises(DatasetIngestionError):
        validate_draft(draft, root, "market")


def test_tampering_and_silent_overwrite_rejected(tmp_path):
    source = write_source(tmp_path, "market.json", market_payload())
    root = tmp_path / "governed"
    draft = import_draft(
        source, root, "market",
        dataset_version="technical-v1",
        source_license="technical fixture",
        original_units={"price": "INR/quintal"}, imported_at=NOW,
    )
    changed = json.loads(draft.read_text(encoding="utf-8"))
    changed["records"][0]["market"] = "Tampered"
    draft.write_text(json.dumps(changed), encoding="utf-8")
    with pytest.raises(DatasetIngestionError, match="digest mismatch"):
        validate_draft(draft, root, "market")


def test_approval_authorization_and_rejection_audit(tmp_path):
    source = write_source(tmp_path, "scheme.json", scheme_payload())
    root = tmp_path / "governed"
    validated = validate_draft(import_draft(
        source, root, "scheme", dataset_version="technical-v1",
        source_license="technical fixture", original_units={}, imported_at=NOW,
    ), root, "scheme")
    with pytest.raises(DatasetIngestionError, match="Admin"):
        approve_validated(
            validated, root, "scheme", approved_by="unauthorized-reviewer",
            reviewer_role="ml_team", approved_at=NOW,
        )
    rejected = reject_validated(
        validated, root, "scheme", rejected_by="authorized-reviewer",
        reviewer_role="admin", reason="Official effective date is not established.",
        rejected_at=NOW,
    )
    decision = json.loads(rejected.read_text(encoding="utf-8"))["governance"]
    assert decision["status"] == "rejected"
    assert decision["decision_id"]
