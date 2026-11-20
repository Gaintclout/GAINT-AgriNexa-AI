"""Ensure villages belong to their selected mandal and district."""
from fastapi import HTTPException
from sqlalchemy.orm import Session
from .models import District, Mandal

def validate_village_hierarchy(db: Session, district_code: str, mandal_code: str | None) -> None:
    if mandal_code is None:
        if db.get(District, district_code) is None:
            raise HTTPException(status_code=422, detail="Unknown district_code")
        return
    mandal = db.get(Mandal, mandal_code)
    if mandal is None:
        raise HTTPException(status_code=422, detail="Unknown mandal_code")
    if mandal.district_code != district_code:
        raise HTTPException(status_code=422, detail="Mandal does not belong to district")
