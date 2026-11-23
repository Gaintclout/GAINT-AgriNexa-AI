"""Protected village and parcel registry backed by PostgreSQL/PostGIS."""

from datetime import datetime
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field, field_validator
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

read_roles = (
    Role.admin,
    Role.gis_operator,
    Role.officer,
    Role.field_verifier,
    Role.ml_team,
)

parcel_read_roles = (*read_roles, Role.farmer)


# --------------------------------------------------
# Request and response schemas
# --------------------------------------------------

class VillageInput(BaseModel):
    code: str = Field(min_length=1, max_length=100)
    name: str = Field(min_length=1, max_length=255)
    district_code: str = Field(min_length=1, max_length=100)
    mandal_code: str | None = Field(
        default=None,
        min_length=1,
        max_length=100,
    )


class ParcelInput(BaseModel):
    external_id: str = Field(min_length=1, max_length=100)
    village_code: str = Field(min_length=1, max_length=100)
    area_hectares: Decimal = Field(
        gt=0,
        max_digits=12,
        decimal_places=4,
    )
    farmer_id: str | None = Field(
        default=None,
        min_length=1,
        max_length=36,
    )

    @field_validator("external_id", "village_code")
    @classmethod
    def validate_identifiers(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Field cannot be blank")
        return value


class ParcelUpdateInput(BaseModel):
    external_id: str | None = Field(
        default=None,
        min_length=1,
        max_length=100,
    )
    village_code: str | None = Field(
        default=None,
        min_length=1,
        max_length=100,
    )
    area_hectares: Decimal | None = Field(
        default=None,
        gt=0,
        max_digits=12,
        decimal_places=4,
    )

    @field_validator("external_id", "village_code")
    @classmethod
    def validate_identifiers(cls, value: str | None) -> str | None:
        if value is None:
            return value

        value = value.strip()

        if not value:
            raise ValueError("Field cannot be blank")

        return value


class ParcelOutput(ParcelInput):
    id: str
    created_at: datetime


class ParcelOwnerInput(BaseModel):
    farmer_id: str | None = Field(
        default=None,
        min_length=1,
        max_length=36,
    )


class FarmerOutput(BaseModel):
    id: str
    email: str

    model_config = {"from_attributes": True}


# --------------------------------------------------
# Shared validation
# --------------------------------------------------

def validate_farmer(
    db: Session,
    farmer_id: str | None,
) -> None:
    if farmer_id is None:
        return

    farmer = db.get(User, farmer_id)

    if (
        farmer is None
        or not farmer.is_active
        or farmer.role != Role.farmer.value
    ):
        raise HTTPException(
            status_code=422,
            detail="farmer_id must identify an active farmer",
        )


def validate_village(
    db: Session,
    village_code: str,
) -> None:
    if db.get(Village, village_code) is None:
        raise HTTPException(
            status_code=422,
            detail="Unknown village_code",
        )


# --------------------------------------------------
# Village management
# --------------------------------------------------

@router.post(
    "/villages",
    response_model=VillageInput,
    status_code=201,
)
def create_village(
    body: VillageInput,
    _user: Principal = Depends(
        require_active_roles(*edit_roles)
    ),
    db: Session = Depends(get_db),
):
    validate_village_hierarchy(
        db,
        body.district_code,
        body.mandal_code,
    )

    village = Village(**body.model_dump())

    db.add(village)

    try:
        db.commit()
        db.refresh(village)

    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=409,
            detail="Village code already exists",
        )

    return village


@router.get(
    "/villages",
    response_model=list[VillageInput],
)
def list_villages(
    _user: Principal = Depends(
        require_active_roles(*read_roles)
    ),
    db: Session = Depends(get_db),
):
    return db.scalars(
        select(Village)
        .order_by(Village.code)
        .limit(100)
    ).all()


# --------------------------------------------------
# Parcel registration
# --------------------------------------------------

@router.post(
    "/parcels",
    response_model=ParcelOutput,
    status_code=201,
)
def create_parcel(
    body: ParcelInput,
    _user: Principal = Depends(
        require_active_roles(*edit_roles)
    ),
    db: Session = Depends(get_db),
):
    validate_village(db, body.village_code)

    validate_farmer(db, body.farmer_id)

    parcel = Parcel(**body.model_dump())

    db.add(parcel)

    try:
        db.commit()
        db.refresh(parcel)

    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=409,
            detail="Parcel external_id already exists",
        )

    return parcel


# --------------------------------------------------
# Parcel ownership
# --------------------------------------------------

@router.patch(
    "/parcels/{parcel_id}/owner",
    response_model=ParcelOutput,
)
def assign_parcel_owner(
    parcel_id: str,
    body: ParcelOwnerInput,
    _user: Principal = Depends(
        require_active_roles(*edit_roles)
    ),
    db: Session = Depends(get_db),
):
    parcel = db.get(Parcel, parcel_id)

    if parcel is None:
        raise HTTPException(
            status_code=404,
            detail="Parcel not found",
        )

    validate_farmer(db, body.farmer_id)

    parcel.farmer_id = body.farmer_id

    try:
        db.commit()
        db.refresh(parcel)

    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=409,
            detail="Parcel ownership update conflicts with existing data",
        )

    return parcel


# --------------------------------------------------
# Active farmer directory
# --------------------------------------------------

@router.get(
    "/users/farmers",
    response_model=list[FarmerOutput],
)
def list_active_farmers(
    _user: Principal = Depends(
        require_active_roles(*edit_roles)
    ),
    db: Session = Depends(get_db),
):
    return db.scalars(
        select(User)
        .where(
            User.role == Role.farmer.value,
            User.is_active.is_(True),
        )
        .order_by(User.email)
        .limit(500)
    ).all()


# --------------------------------------------------
# Parcel listing and search
# --------------------------------------------------

@router.get(
    "/parcels",
    response_model=list[ParcelOutput],
)
def list_parcels(
    search: str | None = Query(
        default=None,
        max_length=100,
    ),
    village_code: str | None = Query(
        default=None,
        min_length=1,
        max_length=100,
    ),
    limit: int = Query(
        default=100,
        ge=1,
        le=100,
    ),
    offset: int = Query(
        default=0,
        ge=0,
        le=100000,
    ),
    _user: Principal = Depends(
        require_active_roles(*parcel_read_roles)
    ),
    db: Session = Depends(get_db),
):
    query = select(Parcel)

    # Farmers can only view their own parcels.
    if _user.role == Role.farmer:
        query = query.where(
            Parcel.farmer_id == _user.subject
        )

    if village_code:
        query = query.where(
            Parcel.village_code == village_code.strip()
        )

    term = (search or "").strip()

    if term:
        escaped = (
            term.replace("\\", "\\\\")
            .replace("%", "\\%")
            .replace("_", "\\_")
        )

        pattern = f"%{escaped}%"

        query = query.where(
            or_(
                Parcel.id.ilike(pattern, escape="\\"),
                Parcel.external_id.ilike(
                    pattern,
                    escape="\\",
                ),
                Parcel.village_code.ilike(
                    pattern,
                    escape="\\",
                ),
            )
        )

    return db.scalars(
        query
        .order_by(
            Parcel.created_at.desc(),
            Parcel.id,
        )
        .offset(offset)
        .limit(limit)
    ).all()


# --------------------------------------------------
# Parcel details
# --------------------------------------------------

@router.get(
    "/parcels/{parcel_id}",
    response_model=ParcelOutput,
)
def get_parcel(
    parcel_id: str,
    _user: Principal = Depends(
        require_active_roles(*parcel_read_roles)
    ),
    db: Session = Depends(get_db),
):
    parcel = db.get(Parcel, parcel_id)

    if parcel is None:
        raise HTTPException(
            status_code=404,
            detail="Parcel not found",
        )

    if (
        _user.role == Role.farmer
        and parcel.farmer_id != _user.subject
    ):
        raise HTTPException(
            status_code=404,
            detail="Parcel not found",
        )

    return parcel


# --------------------------------------------------
# Parcel editing
# --------------------------------------------------

@router.patch(
    "/parcels/{parcel_id}",
    response_model=ParcelOutput,
)
def update_parcel(
    parcel_id: str,
    body: ParcelUpdateInput,
    _user: Principal = Depends(
        require_active_roles(*edit_roles)
    ),
    db: Session = Depends(get_db),
):
    parcel = db.get(Parcel, parcel_id)

    if parcel is None:
        raise HTTPException(
            status_code=404,
            detail="Parcel not found",
        )

    changes = body.model_dump(exclude_unset=True)

    if not changes:
        raise HTTPException(
            status_code=422,
            detail="No changes provided",
        )

    # Explicit null values are not permitted.
    for field, value in changes.items():
        if value is None:
            raise HTTPException(
                status_code=422,
                detail=f"{field} cannot be null",
            )

    if "village_code" in changes:
        validate_village(
            db,
            changes["village_code"],
        )

    # Only fields declared in ParcelUpdateInput
    # are allowed to change.
    for field, value in changes.items():
        setattr(parcel, field, value)

    try:
        db.commit()
        db.refresh(parcel)

    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=409,
            detail="Parcel external_id already exists",
        )

    return parcel
