"""No database required: verify API schema and input validation."""
from datetime import datetime, timedelta, timezone
import pytest
from pydantic import ValidationError
from app.field_verification_router import EvidenceInput, ReviewInput
from app.main import app


def test_new_routes_in_openapi():
    paths = app.openapi()['paths']
    assert '/api/v1/field-verification/evidence' in paths
    assert '/api/v1/field-verification/evidence/{evidence_id}/review' in paths
    assert '/api/v1/field-verification/evidence/{evidence_id}/audit' in paths
    assert '/api/v1/field-verification/evidence/{evidence_id}/photo' in paths


def test_reject_future_timestamp_and_bad_coordinates():
    sample = dict(client_record_id='device_123', parcel_id='0'*36, observation='Crop is healthy', latitude=17.5, longitude=78.5, captured_at=datetime.now(timezone.utc))
    EvidenceInput(**sample)
    with pytest.raises(ValidationError):
        EvidenceInput(**{**sample, 'latitude': 100})
    with pytest.raises(ValidationError):
        EvidenceInput(**{**sample, 'captured_at': datetime.now(timezone.utc) + timedelta(days=1)})
    with pytest.raises(ValidationError):
        EvidenceInput(**{**sample, 'captured_at': datetime.now().replace(tzinfo=None)})


def test_review_decision_enum():
    ReviewInput(decision='approved')
    with pytest.raises(ValidationError):
        ReviewInput(decision='unknown')
