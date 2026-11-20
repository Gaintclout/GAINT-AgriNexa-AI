"""Role-protected state/district/mandal geography master data."""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from .authorization import require_active_roles
from .database import get_db
from .models import State, District, Mandal
from .security import Role, Principal

router = APIRouter(prefix="/api/v1/geography", tags=["geography"])
writers = (Role.admin, Role.gis_operator)
readers = (Role.admin, Role.gis_operator, Role.officer, Role.field_verifier, Role.ml_team)

class StateIn(BaseModel):
    code: str = Field(min_length=1, max_length=100)
    name: str = Field(min_length=1, max_length=255)

class DistrictIn(StateIn):
    state_code: str

class MandalIn(StateIn):
    district_code: str

def commit(db: Session, obj, label: str):
    db.add(obj)
    try:
        db.commit()
        db.refresh(obj)
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, f"{label} code already exists")
    return obj

@router.post("/states", response_model=StateIn, status_code=201)
def add_state(body: StateIn, _: Principal = Depends(require_active_roles(*writers)), db: Session = Depends(get_db)):
    return commit(db, State(**body.model_dump()), "State")

@router.get("/states", response_model=list[StateIn])
def states(_: Principal = Depends(require_active_roles(*readers)), db: Session = Depends(get_db)):
    return db.scalars(select(State).order_by(State.code).limit(100)).all()

@router.post("/districts", response_model=DistrictIn, status_code=201)
def add_district(body: DistrictIn, _: Principal = Depends(require_active_roles(*writers)), db: Session = Depends(get_db)):
    if db.get(State, body.state_code) is None:
        raise HTTPException(422, "Unknown state_code")
    return commit(db, District(**body.model_dump()), "District")

@router.get("/districts", response_model=list[DistrictIn])
def districts(state_code: str | None = None, _: Principal = Depends(require_active_roles(*readers)), db: Session = Depends(get_db)):
    stmt = select(District)
    if state_code is not None:
        stmt = stmt.where(District.state_code == state_code)
    return db.scalars(stmt.order_by(District.code).limit(100)).all()

@router.post("/mandals", response_model=MandalIn, status_code=201)
def add_mandal(body: MandalIn, _: Principal = Depends(require_active_roles(*writers)), db: Session = Depends(get_db)):
    if db.get(District, body.district_code) is None:
        raise HTTPException(422, "Unknown district_code")
    return commit(db, Mandal(**body.model_dump()), "Mandal")

@router.get("/mandals", response_model=list[MandalIn])
def mandals(district_code: str | None = None, _: Principal = Depends(require_active_roles(*readers)), db: Session = Depends(get_db)):
    stmt = select(Mandal)
    if district_code is not None:
        stmt = stmt.where(Mandal.district_code == district_code)
    return db.scalars(stmt.order_by(Mandal.code).limit(100)).all()
