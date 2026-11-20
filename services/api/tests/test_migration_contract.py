from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
def test_migration_is_versioned():
    text = (ROOT / "migrations/versions/0001_identity_geo.py").read_text()
    assert 'revision = "0001_identity_geo"' in text
    assert "CREATE EXTENSION IF NOT EXISTS postgis" in text
    assert "USING GIST (geom)" in text
def test_no_automatic_migrations_at_startup():
    main = (ROOT / "app/main.py").read_text()
    assert "create_all(" not in main
    assert "alembic upgrade" not in main

def test_api_image_installs_runtime_database_and_raster_dependencies():
    dockerfile = (ROOT / "Dockerfile").read_text()
    requirements = (ROOT / "requirements.txt").read_text()
    assert "COPY requirements.txt ./requirements.txt" in dockerfile
    assert "pip install --no-cache-dir --requirement requirements.txt" in dockerfile
    assert "USER 10001:10001" in dockerfile
    for dependency in ("SQLAlchemy==", "alembic==", "psycopg[binary]==", "GeoAlchemy2==", "rasterio=="):
        assert dependency in requirements
