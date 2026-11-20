import pytest
from app.production_config import ProductionConfigurationError, validate_production_configuration

def configure(monkeypatch):
    monkeypatch.setenv("AGRINEXA_ENV", "production")
    monkeypatch.setenv("AGRINEXA_JWT_SECRET", "x" * 48)
    monkeypatch.setenv("AGRINEXA_CORS_ORIGINS", "https://agrinexa.example.com")
    monkeypatch.setenv("DATABASE_URL", "postgresql+psycopg://app:secret@private-db/agrinexa?sslmode=require")
    monkeypatch.setenv("AGRINEXA_PRIVATE_PHOTO_DIR", "/var/lib/agrinexa/photos")
    monkeypatch.delenv("AGRINEXA_MARKET_SNAPSHOT_PATH", raising=False)
    monkeypatch.delenv("AGRINEXA_SCHEME_CATALOGUE_PATH", raising=False)

def test_valid_production_configuration(monkeypatch):
    configure(monkeypatch)
    validate_production_configuration()

@pytest.mark.parametrize(("name", "value"), [
    ("AGRINEXA_JWT_SECRET", "short"),
    ("AGRINEXA_CORS_ORIGINS", "http://localhost:5173"),
    ("DATABASE_URL", "postgresql+psycopg://app:secret@db/agrinexa"),
    ("AGRINEXA_PRIVATE_PHOTO_DIR", "relative/path"),
    ("AGRINEXA_MARKET_SNAPSHOT_PATH", "/tmp/unapproved.json"),
])
def test_unsafe_production_configuration_rejected(monkeypatch, name, value):
    configure(monkeypatch)
    monkeypatch.setenv(name, value)
    with pytest.raises(ProductionConfigurationError):
        validate_production_configuration()
