
"""Farmer registration and password login backed by PostgreSQL user records."""

import hashlib
import secrets
import uuid
from datetime import datetime, timedelta, timezone
from urllib.parse import urlsplit

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from pydantic import BaseModel, Field
from sqlalchemy import select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from .database import get_db
from .models import User
from .security import (
    Principal,
    Role,
    create_access_token,
    current_principal,
    hash_password,
    verify_password,
)

router = APIRouter(prefix="/api/v1/auth", tags=["auth"])

# M15_REFRESH_SESSIONS
_REFRESH_COOKIE = "__Host-agrinexa_refresh"
_REFRESH_DAYS = 7


def _hash_refresh(value: str) -> str:
    """Return the SHA-256 digest of a refresh token."""
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _origin_guard(request: Request) -> None:
    """Require same-origin browser requests for cookie-based mutations."""
    origin = request.headers.get("origin")
    fetch_site = request.headers.get("sec-fetch-site")

    if fetch_site and fetch_site not in ("same-origin", "none"):
        raise HTTPException(
            status_code=403,
            detail="Cross-site session operation rejected",
        )

    if not origin:
        raise HTTPException(
            status_code=403,
            detail="Origin required for session operation",
        )

    try:
        supplied = urlsplit(origin)

        forwarded_proto = request.headers.get(
            "x-forwarded-proto",
            request.url.scheme,
        ).split(",")[0].strip()

        expected = (
            f"{forwarded_proto}://"
            f"{request.headers.get('host', request.url.netloc)}"
        )

        target = urlsplit(expected)

        if (
            supplied.scheme not in ("http", "https")
            or not supplied.netloc
            or supplied.username is not None
            or supplied.password is not None
            or supplied.path not in ("", "/")
            or supplied.query
            or supplied.fragment
            or (supplied.scheme, supplied.netloc)
            != (target.scheme, target.netloc)
        ):
            raise ValueError("Origin mismatch")

    except (ValueError, AttributeError):
        raise HTTPException(
            status_code=403,
            detail="Origin not permitted",
        )


def _set_refresh_cookie(response: Response, token: str) -> None:
    """Set the secure refresh-session cookie."""
    response.set_cookie(
        key=_REFRESH_COOKIE,
        value=token,
        max_age=_REFRESH_DAYS * 86400,
        path="/",
        secure=True,
        httponly=True,
        samesite="strict",
    )


def _delete_refresh_cookie(response: Response) -> None:
    """Delete the refresh cookie using matching attributes."""
    response.delete_cookie(
        key=_REFRESH_COOKIE,
        path="/",
        secure=True,
        httponly=True,
        samesite="strict",
    )


def _issue_refresh(
    db: Session,
    user_id: str,
    response: Response,
) -> None:
    """Create and persist a new refresh session."""
    token = secrets.token_urlsafe(48)
    now = datetime.now(timezone.utc)

    db.execute(
        text("""
            INSERT INTO auth_refresh_sessions
                (id, user_id, token_hash, created_at, expires_at, revoked_at)
            VALUES
                (:id, :uid, :digest, :created, :expires, NULL)
        """),
        {
            "id": str(uuid.uuid4()),
            "uid": user_id,
            "digest": _hash_refresh(token),
            "created": now,
            "expires": now + timedelta(days=_REFRESH_DAYS),
        },
    )

    db.commit()
    _set_refresh_cookie(response, token)


class RegisterFarmer(BaseModel):
    email: str = Field(
        min_length=3,
        max_length=254,
        pattern=r"^[^\s@]+@[^\s@]+\.[^\s@]+$",
    )
    password: str = Field(min_length=12, max_length=128)


class LoginRequest(BaseModel):
    email: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int = 900


class RegistrationResponse(BaseModel):
    id: str
    email: str
    role: Role


@router.post(
    "/register/farmer",
    response_model=RegistrationResponse,
    status_code=status.HTTP_201_CREATED,
)
def register_farmer(
    body: RegisterFarmer,
    db: Session = Depends(get_db),
):
    email = body.email.strip().lower()

    if db.scalar(select(User.id).where(User.email == email)):
        raise HTTPException(
            status_code=409,
            detail="Email already registered",
        )

    user = User(
        email=email,
        password_hash=hash_password(body.password),
        role=Role.farmer.value,
    )

    db.add(user)

    try:
        db.commit()
        db.refresh(user)

    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=409,
            detail="Email already registered",
        )

    return RegistrationResponse(
        id=user.id,
        email=user.email,
        role=Role.farmer,
    )


@router.post("/login", response_model=TokenResponse)
def login(
    body: LoginRequest,
    response: Response,
    request: Request,
    db: Session = Depends(get_db),
):
    email = body.email.strip().lower()

    user = db.scalar(
        select(User).where(User.email == email)
    )

    if (
        user is None
        or not user.is_active
        or not verify_password(body.password, user.password_hash)
    ):
        raise HTTPException(
            status_code=401,
            detail="Invalid credentials",
        )

    try:
        role = Role(user.role)

    except ValueError:
        raise HTTPException(
            status_code=403,
            detail="Account role is not supported",
        )

    # Preserve bearer-token login for non-browser clients.
    # Issue refresh cookies only for validated browser origins.
    if request.headers.get("origin"):
        _origin_guard(request)
        _issue_refresh(db, user.id, response)

    return TokenResponse(
        access_token=create_access_token(user.id, role),
    )


@router.get("/me", response_model=Principal)
def me(
    principal: Principal = Depends(current_principal),
    db: Session = Depends(get_db),
):
    user = db.get(User, principal.subject)

    if (
        user is None
        or not user.is_active
        or user.role != principal.role.value
    ):
        raise HTTPException(
            status_code=401,
            detail="Account no longer active",
        )

    return principal


@router.post("/refresh", response_model=TokenResponse)
def refresh(
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
):
    _origin_guard(request)

    token = request.cookies.get(_REFRESH_COOKIE)

    if not token:
        raise HTTPException(
            status_code=401,
            detail="Session required",
        )

    now = datetime.now(timezone.utc)
    digest = _hash_refresh(token)

    # Atomically consume the existing refresh token.
    # Replayed and concurrent refresh requests fail closed.
    record = db.execute(
        text("""
            UPDATE auth_refresh_sessions
            SET revoked_at = :now
            WHERE token_hash = :digest
              AND revoked_at IS NULL
              AND expires_at > :now
            RETURNING user_id
        """),
        {
            "now": now,
            "digest": digest,
        },
    ).first()

    if record is None:
        db.rollback()

        # Preserve HTTPException behavior expected by security tests.
        raise HTTPException(
            status_code=401,
            detail="Session expired or revoked",
        )

    user = db.get(User, record[0])

    if user is None or not user.is_active:
        db.commit()
        raise HTTPException(
            status_code=401,
            detail="Account no longer active",
        )

    try:
        role = Role(user.role)

    except ValueError:
        db.commit()
        raise HTTPException(
            status_code=403,
            detail="Account role is not supported",
        )

    # _issue_refresh commits the old-token revocation and replacement
    # together before returning the new cookie.
    _issue_refresh(db, user.id, response)

    return TokenResponse(
        access_token=create_access_token(user.id, role),
    )


@router.post("/logout", status_code=204)
def logout_session(
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
):
    _origin_guard(request)

    token = request.cookies.get(_REFRESH_COOKIE)

    if token:
        db.execute(
            text("""
                UPDATE auth_refresh_sessions
                SET revoked_at = :now
                WHERE token_hash = :digest
                  AND revoked_at IS NULL
            """),
            {
                "now": datetime.now(timezone.utc),
                "digest": _hash_refresh(token),
            },
        )

        db.commit()

    # Always delete the browser refresh cookie.
    # Logout remains successful even without an existing session.
    _delete_refresh_cookie(response)
    response.status_code = status.HTTP_204_NO_CONTENT

    return response
