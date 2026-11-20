"""Provision seven local test accounts in gaint_ai_agri_dev only."""

import os
from sqlalchemy import select, text
from app.database import session_factory
from app.models import User
from app.security import Role, hash_password, verify_password

TARGET_DATABASE = "gaint_ai_agri_dev"
TARGET_REVISION = "0011_persistent_auth_sessions"

ACCOUNTS = (
    ("admin.test@agrinexa.example", Role.admin),
    ("gis.test@agrinexa.example", Role.gis_operator),
    ("farmer1.test@agrinexa.example", Role.farmer),
    ("farmer2.test@agrinexa.example", Role.farmer),
    ("verifier1.test@agrinexa.example", Role.field_verifier),
    ("verifier2.test@agrinexa.example", Role.field_verifier),
    ("officer.test@agrinexa.example", Role.officer),
)


def main():
    password = os.environ.get("AGRINEXA_LOCAL_TEST_PASSWORD")
    if not password:
        raise RuntimeError("Missing AGRINEXA_LOCAL_TEST_PASSWORD")

    with session_factory()() as db:
        with db.begin():
            database = db.execute(
                text("SELECT current_database()")
            ).scalar_one()

            revision = db.execute(
                text("SELECT version_num FROM alembic_version")
            ).scalar_one()

            if database != TARGET_DATABASE:
                raise RuntimeError("STOP: Incorrect database")

            if revision != TARGET_REVISION:
                raise RuntimeError("STOP: Unexpected migration revision")

            existing = db.scalars(
                select(User).where(
                    User.email.in_([email for email, _ in ACCOUNTS])
                )
            ).all()
            existing_by_email = {user.email: user for user in existing}

            for email, role in ACCOUNTS:
                user = existing_by_email.get(email)

                if user is not None:
                    if user.role != role.value or not user.is_active:
                        raise RuntimeError(
                            f"STOP: Existing account has unexpected state: {email}"
                        )
                    if not verify_password(password, user.password_hash):
                        raise RuntimeError(
                            f"STOP: Existing password differs: {email}"
                        )
                    continue

                db.add(
                    User(
                        email=email,
                        password_hash=hash_password(password),
                        role=role.value,
                        is_active=True,
                    )
                )

    print("SUCCESS: Seven local test accounts verified.")
    print("Database:", TARGET_DATABASE)
    print("Passwords were not printed.")


if __name__ == "__main__":
    main()
