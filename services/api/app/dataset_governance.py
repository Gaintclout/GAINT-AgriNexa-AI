"""Approval metadata checks for locally governed agent datasets."""

from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
from hashlib import sha256
import json


class DatasetGovernanceError(ValueError):
    pass


def canonical_dataset_hash(payload: dict) -> str:
    content = deepcopy(payload)
    content.pop("governance", None)
    encoded = json.dumps(
        content,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode("utf-8")
    return sha256(encoded).hexdigest()


def parse_governance_timestamp(value, label):
    if not isinstance(value, str):
        raise DatasetGovernanceError(f"Missing {label}")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise DatasetGovernanceError(f"Invalid {label}") from exc
    if parsed.tzinfo is None or parsed > datetime.now(timezone.utc):
        raise DatasetGovernanceError(f"Invalid {label}")
    return parsed


def validate_approved_governance(payload, *, dataset_kind, required_unit=None):
    governance = payload.get("governance")
    if not isinstance(governance, dict):
        raise DatasetGovernanceError("Dataset approval metadata missing")
    if governance.get("status") != "approved":
        raise DatasetGovernanceError("Dataset is not approved")
    if governance.get("dataset_kind") != dataset_kind:
        raise DatasetGovernanceError("Dataset kind mismatch")
    version = governance.get("dataset_version")
    if not isinstance(version, str) or not version.strip() or len(version) > 100:
        raise DatasetGovernanceError("Invalid dataset version")
    license_name = governance.get("source_license")
    if not isinstance(license_name, str) or not license_name.strip() or len(license_name) > 200:
        raise DatasetGovernanceError("Source license is required")
    imported_at = parse_governance_timestamp(governance.get("imported_at"), "import timestamp")
    approved_at = parse_governance_timestamp(governance.get("approved_at"), "approval timestamp")
    if approved_at < imported_at:
        raise DatasetGovernanceError("Approval predates import")
    approver = governance.get("approved_by")
    if not isinstance(approver, str) or len(approver.strip()) < 3 or len(approver) > 100:
        raise DatasetGovernanceError("Invalid dataset approver")
    units = governance.get("original_units")
    if not isinstance(units, dict):
        raise DatasetGovernanceError("Original units are required")
    if required_unit and units.get("price") != required_unit:
        raise DatasetGovernanceError("Unsupported market price unit")
    digest = governance.get("content_sha256")
    if digest != canonical_dataset_hash(payload):
        raise DatasetGovernanceError("Dataset content digest mismatch")
    return governance
