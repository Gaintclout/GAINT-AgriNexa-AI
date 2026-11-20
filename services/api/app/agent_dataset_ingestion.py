"""Controlled draft, validation, and approval workflow for agent datasets."""

from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Literal
from urllib.parse import urlparse

from .dataset_governance import canonical_dataset_hash
from .market_agent import MarketDataError, validate_market_record
from .scheme_agent import SchemeDataError, validate_record


DatasetKind = Literal["market", "scheme"]
MAX_IMPORT_BYTES = 2_000_000


class DatasetIngestionError(ValueError):
    pass


def _read(path: Path):
    if not path.is_absolute() or not path.is_file():
        raise DatasetIngestionError("Import source must be an existing absolute file")
    if path.stat().st_size > MAX_IMPORT_BYTES:
        raise DatasetIngestionError("Import source exceeds size limit")
    try:
        payload = json.loads(path.read_bytes())
    except (OSError, ValueError, UnicodeError) as exc:
        raise DatasetIngestionError("Import source is not valid JSON") from exc
    if not isinstance(payload, dict):
        raise DatasetIngestionError("Dataset root must be an object")
    return payload


def _write_once(path: Path, payload: dict):
    path.parent.mkdir(parents=True, exist_ok=True)
    encoded = json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False) + "\n"
    if path.exists():
        if path.read_text(encoding="utf-8") == encoded:
            return path
        raise DatasetIngestionError("Refusing to overwrite an existing dataset")
    try:
        with path.open("x", encoding="utf-8", newline="\n") as stream:
            stream.write(encoded)
    except FileExistsError as exc:
        raise DatasetIngestionError("Refusing to overwrite an existing dataset") from exc
    return path


def _validate_payload(kind: DatasetKind, payload: dict):
    if payload.get("schema_version") != 2:
        raise DatasetIngestionError("Only schema version 2 can enter approval workflow")
    try:
        if kind == "market":
            required = ("snapshot_id", "published_at", "source_name", "source_url")
            records = payload.get("records")
            if not isinstance(records, list) or not records:
                raise DatasetIngestionError("Market records are required")
            validated = [validate_market_record(item, schema_version=2) for item in records]
            ids = [(
                item.market_id.casefold(), item.commodity,
                (item.variety or "").casefold(), (item.grade or "").casefold(),
                item.price_date,
            ) for item in validated]
            if len(ids) != len(set(ids)):
                raise DatasetIngestionError("Duplicate market identifiers")
        elif kind == "scheme":
            required = ("catalogue_id", "published_at", "authority_name", "authority_source_url")
            records = payload.get("schemes")
            if not isinstance(records, list) or not records:
                raise DatasetIngestionError("Scheme records are required")
            validated = [validate_record(item, schema_version=2) for item in records]
            ids = [item["scheme_id"].casefold() for item in validated]
            if len(ids) != len(set(ids)):
                raise DatasetIngestionError("Duplicate scheme identifiers")
        else:
            raise DatasetIngestionError("Unsupported dataset kind")
        for key in required:
            value = payload.get(key)
            if not isinstance(value, str) or not value.strip():
                raise DatasetIngestionError(f"Missing dataset field: {key}")
        source_url = payload["source_url" if kind == "market" else "authority_source_url"]
        parsed = urlparse(source_url)
        if parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password:
            raise DatasetIngestionError("Dataset source URL must be public HTTPS")
        try:
            published = datetime.fromisoformat(payload["published_at"].replace("Z", "+00:00"))
        except ValueError as exc:
            raise DatasetIngestionError("Invalid dataset publication timestamp") from exc
        if published.tzinfo is None or published > datetime.now(timezone.utc):
            raise DatasetIngestionError("Invalid dataset publication timestamp")
    except (MarketDataError, SchemeDataError) as exc:
        raise DatasetIngestionError(str(exc)) from exc


def import_draft(source: Path, root: Path, kind: DatasetKind, *, dataset_version: str, source_license: str, original_units: dict, imported_at=None):
    payload = _read(source)
    timestamp = imported_at or datetime.now(timezone.utc)
    if timestamp.tzinfo is None or timestamp > datetime.now(timezone.utc):
        raise DatasetIngestionError("Import timestamp must be timezone-aware and not in the future")
    if not dataset_version.strip() or not source_license.strip():
        raise DatasetIngestionError("Dataset version and source license are required")
    if not isinstance(original_units, dict):
        raise DatasetIngestionError("Original units must be an object")
    if kind == "market" and original_units.get("price") != "INR/quintal":
        raise DatasetIngestionError("Market source unit must be INR/quintal")
    digest = canonical_dataset_hash(payload)
    governed = deepcopy(payload)
    governed["governance"] = {
        "status": "draft",
        "dataset_kind": kind,
        "dataset_version": dataset_version,
        "imported_at": timestamp.isoformat(),
        "source_license": source_license,
        "original_units": original_units,
        "content_sha256": digest,
    }
    identifier = payload.get("snapshot_id" if kind == "market" else "catalogue_id")
    if not isinstance(identifier, str) or not identifier.strip():
        raise DatasetIngestionError("Dataset identifier is required")
    return _write_once(root / "draft" / f"{identifier}--{digest[:12]}.json", governed)


def validate_draft(draft: Path, root: Path, kind: DatasetKind):
    payload = _read(draft)
    governance = payload.get("governance")
    if not isinstance(governance, dict) or governance.get("status") != "draft" or governance.get("dataset_kind") != kind:
        raise DatasetIngestionError("Expected a matching draft dataset")
    if governance.get("content_sha256") != canonical_dataset_hash(payload):
        raise DatasetIngestionError("Draft content digest mismatch")
    _validate_payload(kind, payload)
    validated = deepcopy(payload)
    validated["governance"]["status"] = "validated"
    identifier = payload["snapshot_id" if kind == "market" else "catalogue_id"]
    digest = governance["content_sha256"]
    return _write_once(root / "validated" / f"{identifier}--{digest[:12]}.json", validated)


def _authorized_reviewer(role: str):
    if role != "admin":
        raise DatasetIngestionError("Dataset approval requires an Admin reviewer")


def approve_validated(validated_path: Path, root: Path, kind: DatasetKind, *, approved_by: str, reviewer_role: str, approved_at=None):
    _authorized_reviewer(reviewer_role)
    payload = _read(validated_path)
    governance = payload.get("governance")
    if not isinstance(governance, dict) or governance.get("status") != "validated" or governance.get("dataset_kind") != kind:
        raise DatasetIngestionError("Expected a matching validated dataset")
    if len(approved_by.strip()) < 3 or len(approved_by) > 100:
        raise DatasetIngestionError("A valid approver reference is required")
    if governance.get("content_sha256") != canonical_dataset_hash(payload):
        raise DatasetIngestionError("Validated content digest mismatch")
    _validate_payload(kind, payload)
    timestamp = approved_at or datetime.now(timezone.utc)
    if timestamp.tzinfo is None or timestamp > datetime.now(timezone.utc):
        raise DatasetIngestionError("Approval timestamp must be timezone-aware and not in the future")
    try:
        imported_at = datetime.fromisoformat(
            governance["imported_at"].replace("Z", "+00:00")
        )
    except (KeyError, AttributeError, ValueError) as exc:
        raise DatasetIngestionError("Invalid import timestamp") from exc
    if timestamp < imported_at:
        raise DatasetIngestionError("Approval cannot predate import")
    approved = deepcopy(payload)
    approved["governance"].update({
        "status": "approved",
        "approved_by": approved_by.strip(),
        "approved_by_role": reviewer_role,
        "approved_at": timestamp.isoformat(),
        "decision_id": canonical_dataset_hash({
            "kind": kind, "content_sha256": governance["content_sha256"],
            "decision": "approved", "actor": approved_by.strip(),
            "at": timestamp.isoformat(),
        }),
    })
    identifier = payload["snapshot_id" if kind == "market" else "catalogue_id"]
    digest = governance["content_sha256"]
    return _write_once(root / "approved" / f"{identifier}--{digest[:12]}.json", approved)


def reject_validated(validated_path: Path, root: Path, kind: DatasetKind, *, rejected_by: str, reviewer_role: str, reason: str, rejected_at=None):
    _authorized_reviewer(reviewer_role)
    payload = _read(validated_path)
    governance = payload.get("governance")
    if not isinstance(governance, dict) or governance.get("status") != "validated" or governance.get("dataset_kind") != kind:
        raise DatasetIngestionError("Expected a matching validated dataset")
    if governance.get("content_sha256") != canonical_dataset_hash(payload):
        raise DatasetIngestionError("Validated content digest mismatch")
    if len(rejected_by.strip()) < 3 or len(rejected_by) > 100:
        raise DatasetIngestionError("A valid reviewer reference is required")
    if not isinstance(reason, str) or len(reason.strip()) < 10 or len(reason) > 1000:
        raise DatasetIngestionError("A substantive rejection reason is required")
    timestamp = rejected_at or datetime.now(timezone.utc)
    if timestamp.tzinfo is None or timestamp > datetime.now(timezone.utc):
        raise DatasetIngestionError("Rejection timestamp must be timezone-aware and not future")
    rejected = deepcopy(payload)
    rejected["governance"].update({
        "status": "rejected", "rejected_by": rejected_by.strip(),
        "rejected_by_role": reviewer_role, "rejected_at": timestamp.isoformat(),
        "rejection_reason": reason.strip(),
        "decision_id": canonical_dataset_hash({
            "kind": kind, "content_sha256": governance["content_sha256"],
            "decision": "rejected", "actor": rejected_by.strip(),
            "at": timestamp.isoformat(), "reason": reason.strip(),
        }),
    })
    identifier = payload["snapshot_id" if kind == "market" else "catalogue_id"]
    digest = governance["content_sha256"]
    return _write_once(root / "rejected" / f"{identifier}--{digest[:12]}.json", rejected)
