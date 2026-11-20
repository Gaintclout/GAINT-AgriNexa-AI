"""Idempotently seed synthetic browser-UAT data in agrinexa_uat_test only."""
import json
import os
import secrets
from pathlib import Path
from uuid import NAMESPACE_URL, uuid5

from sqlalchemy import select, text

from app.database import session_factory
from app.models import District, Mandal, Parcel, State, User, Village
from app.security import Role, hash_password, verify_password

TARGET_DATABASE = "agrinexa_uat_test"
TARGET_REVISION = "0007_farmer_parcel_ownership"
STATE_CODE = "UAT-STATE"
DISTRICT_CODE = "UAT-DISTRICT"
MANDAL_CODE = "UAT-MANDAL"
VILLAGE_CODE = "UAT-VILLAGE"

ACCOUNTS = (
    ("admin", "admin.uat@agrinexa.example", Role.admin),
    ("farmer_a", "farmer.a.uat@agrinexa.example", Role.farmer),
    ("farmer_b", "farmer.b.uat@agrinexa.example", Role.farmer),
    ("verifier_a", "verifier.a.uat@agrinexa.example", Role.field_verifier),
    ("verifier_b", "verifier.b.uat@agrinexa.example", Role.field_verifier),
    ("officer", "officer.uat@agrinexa.example", Role.officer),
    ("gis_operator", "gis.operator.uat@agrinexa.example", Role.gis_operator),
    ("ml_team", "ml.team.uat@agrinexa.example", Role.ml_team),
)

PARCELS = (
    ("UAT-PARCEL-UNASSIGNED", None, "POLYGON((78.480 17.380,78.485 17.380,78.485 17.385,78.480 17.385,78.480 17.380))"),
    ("UAT-PARCEL-FARMER-A", "farmer_a", "POLYGON((78.490 17.380,78.495 17.380,78.495 17.385,78.490 17.385,78.490 17.380))"),
    ("UAT-PARCEL-FARMER-B", "farmer_b", "POLYGON((78.500 17.380,78.505 17.380,78.505 17.385,78.500 17.385,78.500 17.380))"),
)


def credentials_path() -> Path:
    raw = os.environ.get("AGRINEXA_UAT_CREDENTIALS_FILE", "").strip()
    if not raw:
        raise RuntimeError("AGRINEXA_UAT_CREDENTIALS_FILE must be an absolute local path outside the repository")
    path = Path(raw).expanduser()
    if not path.is_absolute():
        raise RuntimeError("Credential file path must be absolute")
    return path.resolve()


def assert_target(db) -> None:
    database, revision, postgis, owner_column = db.execute(text("""
        SELECT current_database(),
               (SELECT version_num FROM alembic_version),
               EXISTS (SELECT 1 FROM pg_extension WHERE extname='postgis'),
               EXISTS (SELECT 1 FROM information_schema.columns
                       WHERE table_schema='public' AND table_name='parcels' AND column_name='farmer_id')
    """)).one()
    if database != TARGET_DATABASE or revision != TARGET_REVISION or not postgis or not owner_column:
        raise RuntimeError("STOP: database identity or UAT schema validation failed")


def load_or_create_credentials(path: Path) -> dict:
    if path.exists():
        payload = json.loads(path.read_text(encoding="utf-8"))
        if payload.get("database") != TARGET_DATABASE:
            raise RuntimeError("STOP: credential file belongs to a different database")
        expected = {name for name, _, _ in ACCOUNTS}
        if set(payload.get("accounts", {})) != expected:
            raise RuntimeError("STOP: credential file does not contain the expected UAT account set")
        return payload
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {"database": TARGET_DATABASE, "accounts": {
        name: {"email": email, "role": role.value, "password": secrets.token_urlsafe(27)}
        for name, email, role in ACCOUNTS
    }}
    try:
        with path.open("x", encoding="utf-8") as handle:
            json.dump(payload, handle, indent=2)
            handle.write("\n")
    except Exception:
        path.unlink(missing_ok=True)
        raise
    try:
        os.chmod(path, 0o600)
    except OSError:
        pass
    return payload


def ensure_account(db, name: str, email: str, role: Role, credentials: dict) -> User:
    user = db.scalar(select(User).where(User.email == email))
    password = credentials["accounts"][name]["password"]
    if user is None:
        user = User(email=email, password_hash=hash_password(password), role=role.value, is_active=True)
        db.add(user)
        db.flush()
    elif user.role != role.value or not user.is_active:
        raise RuntimeError(f"STOP: existing UAT account has unexpected state: {email}")
    elif not verify_password(password, user.password_hash):
        raise RuntimeError(f"STOP: existing UAT account password does not match the local credentials file: {email}")
    return user


def main() -> None:
    path = credentials_path()
    with session_factory()() as db:
        users = {}
        with db.begin():
            assert_target(db)
            credentials = load_or_create_credentials(path)
            for name, email, role in ACCOUNTS:
                assert_target(db)
                users[name] = ensure_account(db, name, email, role, credentials)

            assert_target(db)
            if db.get(State, STATE_CODE) is None:
                db.add(State(code=STATE_CODE, name="Synthetic UAT State")); db.flush()
            assert_target(db)
            if db.get(District, DISTRICT_CODE) is None:
                db.add(District(code=DISTRICT_CODE, name="Synthetic UAT District", state_code=STATE_CODE)); db.flush()
            assert_target(db)
            if db.get(Mandal, MANDAL_CODE) is None:
                db.add(Mandal(code=MANDAL_CODE, name="Synthetic UAT Mandal", district_code=DISTRICT_CODE)); db.flush()
            assert_target(db)
            if db.get(Village, VILLAGE_CODE) is None:
                db.add(Village(code=VILLAGE_CODE, name="Synthetic UAT Village", district_code=DISTRICT_CODE, mandal_code=MANDAL_CODE)); db.flush()

            for external_id, owner_name, wkt in PARCELS:
                assert_target(db)
                parcel = db.scalar(select(Parcel).where(Parcel.external_id == external_id))
                expected_owner = users[owner_name].id if owner_name else None
                if parcel is None:
                    parcel = Parcel(id=str(uuid5(NAMESPACE_URL, f"agrinexa:{TARGET_DATABASE}:{external_id}")),
                                    external_id=external_id, village_code=VILLAGE_CODE,
                                    area_hectares=0.25, farmer_id=expected_owner)
                    db.add(parcel); db.flush()
                    db.execute(text("UPDATE parcels SET geom=ST_Multi(ST_GeomFromText(:wkt,4326)) WHERE id=:id"),
                               {"wkt": wkt, "id": parcel.id})
                elif parcel.village_code != VILLAGE_CODE or parcel.farmer_id != expected_owner:
                    raise RuntimeError(f"STOP: existing UAT parcel has unexpected ownership or geography: {external_id}")

        assert_target(db)
        verified = db.execute(text("""
            SELECT count(*) FILTER (WHERE external_id LIKE 'UAT-PARCEL-%'),
                   count(*) FILTER (WHERE external_id='UAT-PARCEL-UNASSIGNED' AND farmer_id IS NULL),
                   count(*) FILTER (WHERE external_id IN ('UAT-PARCEL-FARMER-A','UAT-PARCEL-FARMER-B') AND farmer_id IS NOT NULL),
                   count(*) FILTER (WHERE external_id LIKE 'UAT-PARCEL-%' AND geom IS NOT NULL AND ST_IsValid(geom))
            FROM parcels
        """)).one()
        if tuple(verified) != (3, 1, 2, 3):
            raise RuntimeError("STOP: UAT parcel verification failed")
    print(f"SUCCESS: seeded and verified {len(ACCOUNTS)} accounts, 1 hierarchy, and 3 parcel geometries in {TARGET_DATABASE}")
    print(f"Credentials stored locally at: {path}")
    print("Passwords were not printed.")


if __name__ == "__main__":
    main()
