"""Protected village and parcel registry backed by PostgreSQL/PostGIS."""
from datetime import datetime
from decimal import Decimal
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from .database import get_db
from .models import Parcel, User, Village
from .security import Role, Principal
from .authorization import require_active_roles
from .geography_validation import validate_village_hierarchy

router = APIRouter(prefix="/api/v1", tags=["registry"])
edit_roles = (Role.admin, Role.gis_operator)
read_roles = (Role.admin, Role.gis_operator, Role.officer, Role.field_verifier, Role.ml_team)
parcel_read_roles = (*read_roles, Role.farmer)

class VillageInput(BaseModel):
    code: str = Field(min_length=1, max_length=100)
    name: str = Field(min_length=1, max_length=255)
    district_code: str = Field(min_length=1, max_length=100)
    mandal_code: str | None = Field(default=None, min_length=1, max_length=100)

class ParcelInput(BaseModel):
    external_id: str = Field(min_length=1, max_length=100)
    village_code: str = Field(min_length=1, max_length=100)
    area_hectares: Decimal = Field(gt=0, max_digits=12, decimal_places=4)
    farmer_id: str | None = Field(default=None, min_length=1, max_length=36)

class ParcelOutput(ParcelInput):
    id: str
    created_at: datetime

class ParcelOwnerInput(BaseModel):
    farmer_id: str | None = Field(default=None, min_length=1, max_length=36)

class FarmerOutput(BaseModel):
    id: str
    email: str
    model_config = {'from_attributes': True}

def validate_farmer(db: Session, farmer_id: str | None) -> None:
    if farmer_id is None:
        return
    farmer = db.get(User, farmer_id)
    if farmer is None or not farmer.is_active or farmer.role != Role.farmer.value:
        raise HTTPException(422, "farmer_id must identify an active farmer")

@router.post("/villages", response_model=VillageInput, status_code=201)
def create_village(body: VillageInput, _user: Principal = Depends(require_active_roles(*edit_roles)), db: Session = Depends(get_db)):
    validate_village_hierarchy(db, body.district_code, body.mandal_code)
    village = Village(**body.model_dump())
    db.add(village)
    try:
        db.commit()
        db.refresh(village)
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, "Village code already exists")
    return village

@router.get("/villages", response_model=list[VillageInput])
def list_villages(_user: Principal = Depends(require_active_roles(*read_roles)), db: Session = Depends(get_db)):
    return db.scalars(select(Village).order_by(Village.code).limit(100)).all()

@router.post("/parcels", response_model=ParcelOutput, status_code=201)
def create_parcel(body: ParcelInput, _user: Principal = Depends(require_active_roles(*edit_roles)), db: Session = Depends(get_db)):
    if db.get(Village, body.village_code) is None:
        raise HTTPException(422, "Unknown village_code")
    validate_farmer(db, body.farmer_id)
    parcel = Parcel(**body.model_dump())
    db.add(parcel)
    try:
        db.commit()
        db.refresh(parcel)
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, "Parcel external_id already exists")
    return parcel

@router.patch("/parcels/{parcel_id}/owner", response_model=ParcelOutput)
def assign_parcel_owner(parcel_id: str, body: ParcelOwnerInput, _user: Principal = Depends(require_active_roles(*edit_roles)), db: Session = Depends(get_db)):
    parcel = db.get(Parcel, parcel_id)
    if parcel is None:
        raise HTTPException(404, "Parcel not found")
    validate_farmer(db, body.farmer_id)
    parcel.farmer_id = body.farmer_id
    db.commit()
    db.refresh(parcel)
    return parcel

@router.get("/users/farmers", response_model=list[FarmerOutput])
def list_active_farmers(_user: Principal = Depends(require_active_roles(*edit_roles)), db: Session = Depends(get_db)):
    return db.scalars(select(User).where(User.role == Role.farmer.value, User.is_active.is_(True)).order_by(User.email).limit(500)).all()

@router.get("/parcels", response_model=list[ParcelOutput])
def list_parcels(
    search: str | None = Query(default=None, max_length=100),
    village_code: str | None = Query(default=None, min_length=1, max_length=100),
    limit: int = Query(default=100, ge=1, le=100),
    offset: int = Query(default=0, ge=0, le=100000),
    _user: Principal = Depends(require_active_roles(*parcel_read_roles)),
    db: Session = Depends(get_db),
):
    query = select(Parcel)
    if _user.role == Role.farmer:
        query = query.where(Parcel.farmer_id == _user.subject)
    if village_code:
        query = query.where(Parcel.village_code == village_code.strip())
    term = (search or "").strip()
    if term:
        escaped = term.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
        pattern = f"%{escaped}%"
        query = query.where(or_(
            Parcel.id.ilike(pattern, escape="\\"),
            Parcel.external_id.ilike(pattern, escape="\\"),
            Parcel.village_code.ilike(pattern, escape="\\"),
        ))
    return db.scalars(
        query.order_by(Parcel.created_at.desc(), Parcel.id)
        .offset(offset)
        .limit(limit)
    ).all()

@router.get("/parcels/{parcel_id}", response_model=ParcelOutput)
def get_parcel(parcel_id: str, _user: Principal = Depends(require_active_roles(*parcel_read_roles)), db: Session = Depends(get_db)):
    parcel = db.get(Parcel, parcel_id)
    if parcel is None or (_user.role == Role.farmer and parcel.farmer_id != _user.subject):
        raise HTTPException(404, "Parcel not found")
    return parcel
