"""Authenticated, retry-safe field verification workflow."""
from datetime import datetime, timezone
from typing import Literal
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from .authorization import require_active_roles
from .database import get_db
from .field_verification_models import FieldEvidence, FieldEvidenceAudit
from .models import Parcel
from .security import Principal, Role
from fastapi import File, UploadFile
from fastapi.responses import FileResponse
from .field_photo_storage import MAX_PHOTO_BYTES, private_photo_path, save_private_photo

router = APIRouter(prefix='/api/v1/field-verification', tags=['field-verification'])


class EvidenceInput(BaseModel):
    client_record_id: str = Field(min_length=1, max_length=100, pattern=r'^[A-Za-z0-9_-]+$')
    parcel_id: str = Field(min_length=36, max_length=36)
    observation: str = Field(min_length=1, max_length=4000)
    latitude: float = Field(ge=-90, le=90, allow_inf_nan=False)
    longitude: float = Field(ge=-180, le=180, allow_inf_nan=False)
    captured_at: datetime

    @field_validator('captured_at')
    @classmethod
    def timezone_required(cls, value):
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError('captured_at must contain timezone offset')
        if value.astimezone(timezone.utc) > datetime.now(timezone.utc):
            raise ValueError('captured_at cannot be in the future')
        return value


class EvidenceOutput(BaseModel):
    id: str
    client_record_id: str
    parcel_id: str
    verifier_id: str
    observation: str
    latitude: float
    longitude: float
    captured_at: datetime
    status: str
    photo_sha256: str | None
    reviewer_id: str | None
    review_note: str | None
    reviewed_at: datetime | None
    created_at: datetime
    model_config = {'from_attributes': True}


class ReviewInput(BaseModel):
    decision: Literal['approved', 'rejected', 'correction_requested']
    note: str = Field(default='', max_length=2000)


@router.post('/evidence', response_model=EvidenceOutput, status_code=201)
def submit(body: EvidenceInput, principal: Principal = Depends(require_active_roles(Role.field_verifier)), db: Session = Depends(get_db)):
    existing = db.scalar(select(FieldEvidence).where(FieldEvidence.verifier_id == principal.subject, FieldEvidence.client_record_id == body.client_record_id))
    if existing is not None:
        # Never silently overwrite a submitted record on retry.
        if any(getattr(existing, key) != value for key, value in body.model_dump().items()):
            raise HTTPException(409, 'Client record ID already used with different evidence')
        return existing
    if db.get(Parcel, body.parcel_id) is None:
        raise HTTPException(422, 'Unknown parcel_id')
    record = FieldEvidence(verifier_id=principal.subject, **body.model_dump())
    db.add(record)
    db.flush()
    record.status = 'pending_photo'
    db.add(FieldEvidenceAudit(evidence_id=record.id, actor_id=principal.subject, action='metadata_received'))
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, 'Duplicate client record ID; fetch the existing record')
    db.refresh(record)
    return record


@router.get('/evidence', response_model=list[EvidenceOutput])
def list_evidence(principal: Principal = Depends(require_active_roles(Role.field_verifier, Role.officer, Role.admin)), db: Session = Depends(get_db), limit: int = 50, offset: int = 0):
    if not 1 <= limit <= 100 or not 0 <= offset <= 100000:
        raise HTTPException(422, 'Invalid pagination')
    query = select(FieldEvidence)
    if principal.role == Role.field_verifier:
        query = query.where(FieldEvidence.verifier_id == principal.subject)
    else:
        query = query.where(FieldEvidence.status != 'pending_photo')
    return db.scalars(query.order_by(FieldEvidence.created_at.desc(), FieldEvidence.id).offset(offset).limit(limit)).all()


@router.get('/evidence/{evidence_id}', response_model=EvidenceOutput)
def get_evidence(evidence_id: str, principal: Principal = Depends(require_active_roles(Role.field_verifier, Role.officer, Role.admin)), db: Session = Depends(get_db)):
    record = db.get(FieldEvidence, evidence_id)
    if record is None or (principal.role == Role.field_verifier and record.verifier_id != principal.subject):
        raise HTTPException(404, 'Evidence not found')
    return record


@router.post('/evidence/{evidence_id}/review', response_model=EvidenceOutput)
def review(evidence_id: str, body: ReviewInput, principal: Principal = Depends(require_active_roles(Role.officer, Role.admin)), db: Session = Depends(get_db)):
    record = db.scalar(select(FieldEvidence).where(FieldEvidence.id == evidence_id).with_for_update())
    if record is None:
        raise HTTPException(404, 'Evidence not found')
    if record.status != 'submitted':
        raise HTTPException(409, 'Evidence is not ready for review')
    if not record.photo_sha256:
        raise HTTPException(409, 'Evidence photograph must be uploaded before review')
    if body.decision != 'approved' and not body.note.strip():
        raise HTTPException(422, 'Review note required for rejection or correction')
    record.status = body.decision
    record.review_note = body.note.strip() or None
    record.reviewer_id = principal.subject
    record.reviewed_at = datetime.now(timezone.utc)
    db.add(FieldEvidenceAudit(evidence_id=record.id, actor_id=principal.subject, action=body.decision, note=record.review_note))
    db.commit()
    db.refresh(record)
    return record


class AuditOutput(BaseModel):
    id: str
    evidence_id: str
    actor_id: str
    action: str
    note: str | None
    created_at: datetime
    model_config = {'from_attributes': True}


@router.get('/evidence/{evidence_id}/audit', response_model=list[AuditOutput])
def audit(evidence_id: str, principal: Principal = Depends(require_active_roles(Role.officer, Role.admin)), db: Session = Depends(get_db)):
    if db.get(FieldEvidence, evidence_id) is None:
        raise HTTPException(404, 'Evidence not found')
    return db.scalars(select(FieldEvidenceAudit).where(FieldEvidenceAudit.evidence_id == evidence_id).order_by(FieldEvidenceAudit.created_at).limit(100)).all()

@router.get('/evidence/{evidence_id}/photo')
def get_evidence_photo(evidence_id: str, principal: Principal = Depends(require_active_roles(Role.field_verifier, Role.officer, Role.admin)), db: Session = Depends(get_db)):
    record = db.get(FieldEvidence, evidence_id)
    if record is None or (principal.role == Role.field_verifier and record.verifier_id != principal.subject):
        raise HTTPException(404, 'Evidence not found')
    if not record.photo_sha256 or not record.photo_content_type:
        raise HTTPException(404, 'Evidence photo not found')
    return FileResponse(private_photo_path(record.photo_sha256, record.photo_content_type), media_type=record.photo_content_type,
                        headers={'Cache-Control': 'private, no-store', 'Content-Security-Policy': "default-src 'none'"})

@router.post(
    "/evidence/{evidence_id}/photo",
    response_model=EvidenceOutput,
)
async def upload_evidence_photo(
    evidence_id: str,
    photo: UploadFile = File(...),
    principal: Principal = Depends(
        require_active_roles(Role.field_verifier)
    ),
    db: Session = Depends(get_db),
):
    record = db.scalar(
        select(FieldEvidence)
        .where(FieldEvidence.id == evidence_id)
        .with_for_update()
    )

    if record is None or record.verifier_id != principal.subject:
        raise HTTPException(404, "Evidence not found")

    if record.status not in ("pending_photo", "submitted"):
        raise HTTPException(409, "Photo cannot be changed after review")

    content_type = photo.content_type or ""

    try:
        data = await photo.read(MAX_PHOTO_BYTES + 1)
    finally:
        await photo.close()

    if len(data) > MAX_PHOTO_BYTES:
        raise HTTPException(413, "Photo exceeds 8 MB")

    digest, size = save_private_photo(data, content_type)

    if record.photo_sha256 is not None:
        if (
            record.photo_sha256 == digest
            and record.photo_content_type == content_type
            and record.photo_bytes == size
        ):
            return record

        raise HTTPException(
            409,
            "A different photo is already attached to this evidence",
        )

    if record.status == "submitted":
        raise HTTPException(409, "Evidence is already submitted")

    record.photo_sha256 = digest
    record.photo_content_type = content_type
    record.photo_bytes = size
    record.status = "submitted"

    db.add(
        FieldEvidenceAudit(
            evidence_id=record.id,
            actor_id=principal.subject,
            action="photo_attached",
            note=f"SHA256:{digest}",
        )
    )

    db.add(FieldEvidenceAudit(evidence_id=record.id, actor_id=principal.subject, action="submitted"))
    db.commit()
    db.refresh(record)

    return record
