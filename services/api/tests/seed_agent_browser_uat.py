"""Seed or remove ephemeral users in the guarded M16 disposable database."""

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import create_engine, delete
from sqlalchemy.engine import make_url

from app.models import User
from app.security import hash_password


IDS = {
    "admin": "m16-uat-admin",
    "gis_operator": "m16-uat-gis",
    "ml_team": "m16-uat-ml",
    "farmer": "m16-uat-farmer",
}


def main():
    url = make_url(os.environ["DATABASE_URL"])
    if (
        url.database != "agrinexa_agent_audit_test"
        or url.host != "127.0.0.1"
        or url.port != 55432
    ):
        raise RuntimeError("Refusing non-disposable UAT database")

    engine = create_engine(url, hide_parameters=True)
    try:
        with engine.begin() as connection:
            connection.execute(delete(User).where(User.id.in_(IDS.values())))
            if "--cleanup" not in sys.argv:
                password = os.environ["AGRINEXA_UAT_BROWSER_PASSWORD"]
                password_hash = hash_password(password)
                connection.execute(User.__table__.insert(), [
                    {
                        "id": identifier,
                        "email": f"{identifier}@example.test",
                        "password_hash": password_hash,
                        "role": role,
                        "is_active": True,
                    }
                    for role, identifier in IDS.items()
                ])
    finally:
        engine.dispose()


if __name__ == "__main__":
    main()
