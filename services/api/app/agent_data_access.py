"""Read-only, ownership-validated parcel access for future agents."""

from dataclasses import dataclass
from decimal import Decimal

from fastapi import HTTPException
from sqlalchemy.orm import Session

from .models import Parcel, User
from .security import Principal, Role


@dataclass(frozen=True)
class ParcelContext:
    parcel_id: str
    farmer_id: str
    village_code: str
    area_hectares: Decimal


def load_parcel_context(
    db: Session,
    principal: Principal,
    parcel_id: str,
) -> ParcelContext:
    """Return only authorized, existing parcel information."""

    if principal.role not in (
        Role.admin,
        Role.gis_operator,
        Role.ml_team,
        Role.farmer,
    ):
        raise HTTPException(403, "Role not authorized")

    actor = db.get(User, principal.subject)

    if (
        actor is None
        or not actor.is_active
        or actor.role != principal.role.value
    ):
        raise HTTPException(401, "Account no longer active")

    parcel = db.get(Parcel, parcel_id)

    if parcel is None:
        raise HTTPException(404, "Parcel not found")

    if (
        principal.role == Role.farmer
        and parcel.farmer_id != principal.subject
    ):
        raise HTTPException(404, "Parcel not found")

    if parcel.farmer_id is None:
        raise HTTPException(409, "Parcel has no assigned farmer")

    farmer = db.get(User, parcel.farmer_id)

    if (
        farmer is None
        or not farmer.is_active
        or farmer.role != Role.farmer.value
    ):
        raise HTTPException(409, "Assigned farmer is not active")

    return ParcelContext(
        parcel_id=parcel.id,
        farmer_id=parcel.farmer_id,
        village_code=parcel.village_code,
        area_hectares=Decimal(str(parcel.area_hectares)),
    )
