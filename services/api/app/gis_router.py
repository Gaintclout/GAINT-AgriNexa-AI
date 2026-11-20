"""PostGIS parcel boundary endpoints; require active database accounts."""
import json
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.orm import Session
from .authorization import require_active_roles
from .boundary import normalize_boundary
from .database import get_db
from .models import Parcel
from .security import Role, Principal

router = APIRouter(prefix="/api/v1/parcels", tags=["gis"])
writers = (Role.admin, Role.gis_operator)
readers = (Role.admin, Role.gis_operator, Role.officer, Role.field_verifier, Role.ml_team, Role.farmer)

class BoundaryPayload(BaseModel):
    geometry: dict

def get_existing(db: Session, parcel_id: str, principal: Principal | None = None):
    parcel = db.get(Parcel, parcel_id)
    if parcel is None or (principal is not None and principal.role == Role.farmer and parcel.farmer_id != principal.subject):
        raise HTTPException(404, "Parcel not found")
    return parcel

@router.put("/{parcel_id}/boundary")
def set_boundary(parcel_id: str, body: BoundaryPayload, _: Principal = Depends(require_active_roles(*writers)), db: Session = Depends(get_db)):
    get_existing(db, parcel_id)
    geometry = normalize_boundary(body.geometry)
    serialized = json.dumps(geometry)
    # PostGIS checks self-intersections, degeneracy and invalid polygon topology.
    valid = db.execute(text("SELECT ST_IsValid(ST_SetSRID(ST_GeomFromGeoJSON(:geometry),4326))"), {"geometry": serialized}).scalar_one()
    if not valid:
        raise HTTPException(422, "Invalid polygon topology")
    db.execute(text("UPDATE parcels SET geom = ST_Multi(ST_SetSRID(ST_GeomFromGeoJSON(:geometry),4326)) WHERE id = :id"),
               {"geometry": serialized, "id": parcel_id})
    db.commit()
    return {"parcel_id": parcel_id, "geometry": geometry}

@router.get("/{parcel_id}/boundary")
def get_boundary(parcel_id: str, principal: Principal = Depends(require_active_roles(*readers)), db: Session = Depends(get_db)):
    get_existing(db, parcel_id, principal)
    geometry = db.execute(text("SELECT ST_AsGeoJSON(geom) FROM parcels WHERE id = :id"), {"id": parcel_id}).scalar_one()
    if geometry is None:
        raise HTTPException(404, "Parcel boundary not recorded")
    return {"type": "Feature", "geometry": json.loads(geometry), "properties": {"parcel_id": parcel_id}}
