"""Sprint 1 authentication primitives. No default users or passwords."""
import os
from datetime import datetime, timedelta, timezone
from enum import Enum
from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jwt import DecodeError, ExpiredSignatureError, InvalidTokenError, decode, encode
from pwdlib import PasswordHash
from pydantic import BaseModel

password_hash = PasswordHash.recommended()
bearer = HTTPBearer(auto_error=False)
ALGORITHM = "HS256"


class AuthenticationConfigurationError(RuntimeError):
    pass


class Role(str, Enum):
    farmer = "farmer"
    field_verifier = "field_verifier"
    officer = "officer"
    admin = "admin"
    gis_operator = "gis_operator"
    ml_team = "ml_team"

class Principal(BaseModel):
    subject: str
    role: Role

def hash_password(password: str) -> str:
    if len(password) < 12:
        raise ValueError("Password must contain at least 12 characters")
    return password_hash.hash(password)

def verify_password(password: str, stored_hash: str) -> bool:
    return password_hash.verify(password, stored_hash)

def _secret() -> str:
    secret = os.environ.get("AGRINEXA_JWT_SECRET", "")
    if len(secret) < 32:
        raise AuthenticationConfigurationError("Authentication service is not configured")
    return secret

def create_access_token(subject: str, role: Role, minutes: int = 15) -> str:
    now = datetime.now(timezone.utc)
    return encode({"sub": subject, "role": role.value, "iat": now, "exp": now + timedelta(minutes=minutes)}, _secret(), algorithm=ALGORITHM)

def current_principal(credentials: HTTPAuthorizationCredentials | None = Depends(bearer)) -> Principal:
    if credentials is None:
        raise HTTPException(status_code=401, detail="Authentication required", headers={"WWW-Authenticate": "Bearer"})
    try:
        payload = decode(credentials.credentials, _secret(), algorithms=[ALGORITHM], options={"require": ["sub", "role", "exp"]})
        subject = payload["sub"]
        if not isinstance(subject, str) or not subject.strip():
            raise ValueError("Invalid subject")
        return Principal(subject=subject, role=Role(payload["role"]))
    except (InvalidTokenError, ValueError, KeyError, TypeError):
        raise HTTPException(status_code=401, detail="Invalid or expired token", headers={"WWW-Authenticate": "Bearer"})

def require_roles(*allowed: Role):
    def dependency(principal: Principal = Depends(current_principal)) -> Principal:
        if principal.role not in allowed:
            raise HTTPException(status_code=403, detail="Insufficient permissions")
        return principal
    return dependency
