"""Explicit, fail-closed production migration gate. Never runs on application start."""
import json
import os
from datetime import datetime
from pathlib import Path
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url

EXPECTED_HEAD = "0012_agent_audit_governance"
LOCK_ID = 92422026

def fail(message):
    raise SystemExit(f"STOP: {message}")

def main():
    raw_url = os.getenv("DATABASE_URL", "")
    try:
        url = make_url(raw_url)
    except Exception:
        fail("DATABASE_URL is invalid")
    if url.get_backend_name() != "postgresql" or not url.database:
        fail("PostgreSQL DATABASE_URL is required")
    expected_current = os.getenv("AGRINEXA_EXPECTED_CURRENT_REVISION", "").strip()
    if not expected_current:
        fail("AGRINEXA_EXPECTED_CURRENT_REVISION is required")
    approval_path = Path(os.getenv("AGRINEXA_BACKUP_APPROVAL_FILE", ""))
    if not approval_path.is_absolute() or not approval_path.is_file():
        fail("approved backup evidence file is required")
    try:
        approval = json.loads(approval_path.read_text(encoding="utf-8"))
    except Exception:
        fail("backup evidence is invalid JSON")
    required = ("database", "backup_id", "approved_by", "approved_at")
    if any(not isinstance(approval.get(key), str) or not approval[key].strip() for key in required):
        fail("backup evidence is incomplete")
    if approval["database"] != url.database:
        fail("backup evidence targets a different database")
    try:
        datetime.fromisoformat(approval["approved_at"].replace("Z", "+00:00"))
    except ValueError:
        fail("backup approval timestamp is invalid")

    engine = create_engine(url, pool_pre_ping=True, hide_parameters=True, connect_args={"connect_timeout": 5})
    try:
        with engine.begin() as connection:
            connection.execute(text("SELECT pg_advisory_xact_lock(:lock)"), {"lock": LOCK_ID})
            identity = connection.execute(text("SELECT current_database(), (SELECT version_num FROM alembic_version), EXISTS (SELECT 1 FROM pg_extension WHERE extname='postgis')")).one()
            if identity[0] != url.database or identity[1] != expected_current:
                fail("database identity or current revision differs from approved release input")
            if not identity[2]:
                fail("PostGIS extension is required")
        command.upgrade(Config("alembic.ini"), "head")
        with engine.connect() as connection:
            state = connection.execute(text("""
                SELECT (SELECT version_num FROM alembic_version),
                       EXISTS (SELECT 1 FROM pg_trigger WHERE tgname='trg_agent_audit_append_only' AND NOT tgisinternal),
                       EXISTS (SELECT 1 FROM pg_trigger WHERE tgname='trg_agent_audit_no_truncate' AND NOT tgisinternal)
            """)).one()
            if state != (EXPECTED_HEAD, True, True):
                fail("post-migration schema or audit guards failed verification")
    finally:
        engine.dispose()
    print("Migration verification complete; expected head and audit guards are present.")

if __name__ == "__main__":
    main()
