"""Separate process liveness from operational dependency readiness."""
from pathlib import Path
from fastapi import APIRouter
from fastapi.responses import JSONResponse
from sqlalchemy import text
from .database import make_engine
from .field_photo_storage import storage_root

router = APIRouter(tags=["System"])
EXPECTED_REVISION = "0012_agent_audit_governance"

@router.get("/live")
def liveness():
    return {"status": "ok", "service": "agrinexa-api"}

@router.get("/ready")
def readiness():
    checks = {"database": False, "migration": False, "postgis": False, "photo_storage": False}
    try:
        with make_engine().connect() as connection:
            state = connection.execute(text("SELECT (SELECT version_num FROM alembic_version), EXISTS (SELECT 1 FROM pg_extension WHERE extname = 'postgis')")).one()
            checks.update(database=True, migration=state[0] == EXPECTED_REVISION, postgis=bool(state[1]))
    except Exception:
        pass
    try:
        checks["photo_storage"] = Path(storage_root()).is_dir()
    except Exception:
        pass
    ready = all(checks.values())
    return JSONResponse(status_code=200 if ready else 503, content={"status": "ready" if ready else "not_ready", "checks": checks})
