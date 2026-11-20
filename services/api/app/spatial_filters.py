"""Bounded, parameterized GIS parcel filters."""
from fastapi import HTTPException

def normalize_filter(value: str | None, label: str) -> str | None:
    if value is None:
        return None
    value = value.strip()
    if not 1 <= len(value) <= 100:
        raise HTTPException(status_code=422, detail=f"Invalid {label}")
    return value
