"""Database-backed authorization; never trust a stale JWT role alone."""
from fastapi import Depends, HTTPException
from sqlalchemy.orm import Session
from .database import get_db
from .models import User
from .security import Principal, Role, current_principal

def require_active_roles(*allowed: Role):
    def dependency(principal: Principal = Depends(current_principal), db: Session = Depends(get_db)) -> Principal:
        user = db.get(User, principal.subject)
        if user is None or not user.is_active:
            raise HTTPException(status_code=401, detail="Account inactive or missing")
        if user.role != principal.role.value:
            raise HTTPException(status_code=401, detail="Account role changed; sign in again")
        if principal.role not in allowed:
            raise HTTPException(status_code=403, detail="Insufficient permissions")
        return principal
    return dependency
