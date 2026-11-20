"""Verify committed M17 audit evidence without mutating the database."""

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import create_engine, func, select
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session

from app.agent_audit_models import AgentAuditRecord
from app.models import Parcel, User, Village
OPERATOR_ID = "m17-uat-admin"
FARMER_ID = "m17-uat-farmer"
VILLAGE_CODE = "M17-UAT-VILLAGE"
PARCEL_ID = "17000000-0000-4000-8000-000000000017"


def main():
    url = make_url(os.environ["DATABASE_URL"])
    if (
        url.database != "agrinexa_agent_audit_test"
        or url.host != "127.0.0.1"
        or url.port != 55432
    ):
        raise RuntimeError("Refusing non-disposable M17 database")

    engine = create_engine(url, hide_parameters=True)
    try:
        with Session(engine) as session:
            assert session.scalar(select(func.count()).select_from(User).where(User.id.in_((OPERATOR_ID, FARMER_ID)))) == 2
            assert session.scalar(select(func.count()).select_from(Village).where(Village.code == VILLAGE_CODE)) == 1
            assert session.scalar(select(func.count()).select_from(Parcel).where(Parcel.id == PARCEL_ID, Parcel.farmer_id == FARMER_ID)) == 1
            records = session.scalars(select(AgentAuditRecord).where(
                AgentAuditRecord.actor_id == OPERATOR_ID,
                AgentAuditRecord.parcel_id == PARCEL_ID,
            )).all()
            assert len(records) == 1
            event = records[0]
            assert event.actor_role == "admin"
            assert event.operation == "INTAKE_PROFILE"
            assert event.outcome == "allowed"
            assert event.reason_code == "AUTHORIZED"
            assert event.id
            assert event.created_at is not None
            assert event.created_at.utcoffset() is not None
    finally:
        engine.dispose()


if __name__ == "__main__":
    main()
