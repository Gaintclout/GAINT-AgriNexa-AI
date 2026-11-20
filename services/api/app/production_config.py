"""Fail-fast validation for explicitly selected production mode."""
import os
from pathlib import PurePosixPath
from sqlalchemy.engine import make_url

class ProductionConfigurationError(RuntimeError):
    pass

def validate_production_configuration():
    if os.getenv("AGRINEXA_ENV", "development").casefold() != "production":
        return
    secret = os.getenv("AGRINEXA_JWT_SECRET", "")
    if len(secret) < 48 or secret.startswith("REPLACE"):
        raise ProductionConfigurationError("Production JWT secret is missing or too short")
    origins = [value.strip() for value in os.getenv("AGRINEXA_CORS_ORIGINS", "").split(",") if value.strip()]
    if not origins or any(not value.startswith("https://") or "localhost" in value or "127.0.0.1" in value for value in origins):
        raise ProductionConfigurationError("Production CORS origins must be explicit HTTPS origins")
    try:
        database = make_url(os.getenv("DATABASE_URL", ""))
    except Exception as exc:
        raise ProductionConfigurationError("Production database URL is invalid") from exc
    if database.get_backend_name() != "postgresql" or database.query.get("sslmode") not in ("require", "verify-ca", "verify-full"):
        raise ProductionConfigurationError("Production PostgreSQL must require TLS")
    photo_root = PurePosixPath(os.getenv("AGRINEXA_PRIVATE_PHOTO_DIR", ""))
    if not photo_root.is_absolute():
        raise ProductionConfigurationError("Production photo storage path must be absolute")
    approved_root = PurePosixPath("/var/lib/agrinexa/datasets/approved")
    for name in ("AGRINEXA_MARKET_SNAPSHOT_PATH", "AGRINEXA_SCHEME_CATALOGUE_PATH"):
        value = os.getenv(name, "").strip()
        if value and approved_root not in PurePosixPath(value).parents:
            raise ProductionConfigurationError(f"{name} must reference approved read-only storage")
