"""Seed the minimum M17 Intake/Profile records in the guarded database."""

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import create_engine, select
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session

from app.models import Parcel, User, Village
from app.security import hash_password


OPERATOR_ID = "m17-uat-admin"
FARMER_ID = "m17-uat-farmer"
VILLAGE_CODE = "M17-UAT-VILLAGE"
PARCEL_ID = "17000000-0000-4000-8000-000000000017"


def guarded_url():
    url = make_url(os.environ["DATABASE_URL"])
    if (
        url.database != "agrinexa_agent_audit_test"
        or url.host != "127.0.0.1"
        or url.port != 55432
    ):
        raise RuntimeError("Refusing non-disposable M17 database")
    return url


def main():
    password = os.environ["AGRINEXA_UAT_BROWSER_PASSWORD"]
    engine = create_engine(guarded_url(), hide_parameters=True)
    try:
        with Session(engine) as session:
            if session.scalar(select(User.id).where(User.id.in_((OPERATOR_ID, FARMER_ID)))):
                raise RuntimeError("M17 UAT identities already exist")
            password_hash = hash_password(password)
            session.add_all([
                User(
                    id=OPERATOR_ID,
                    email="m17-uat-admin@example.test",
                    password_hash=password_hash,
                    role="admin",
                    is_active=True,
                ),
                User(
                    id=FARMER_ID,
                    email="m17-uat-farmer@example.test",
                    password_hash=password_hash,
                    role="farmer",
                    is_active=True,
                ),
                Village(
                    code=VILLAGE_CODE,
                    name="M17 Disposable UAT Village",
                    district_code="M17-UAT-DISTRICT",
                ),
            ])
            session.flush()
            session.add(Parcel(
                id=PARCEL_ID,
                external_id="M17-UAT-PARCEL",
                village_code=VILLAGE_CODE,
                farmer_id=FARMER_ID,
                area_hectares=2.5,
                geom=None,
            ))
            session.commit()
    finally:
        engine.dispose()


if __name__ == "__main__":
    main()
