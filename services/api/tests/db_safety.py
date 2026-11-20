from sqlalchemy import create_engine, event
from sqlalchemy.engine import make_url
from sqlalchemy.exc import ArgumentError
from app.database import safe_do_connect

SAFE_DATABASES = frozenset({"agrinexa_test"})
REQUIRED_REVISION = "0007_farmer_parcel_ownership"
DISPOSABLE_DATABASE_MARKER = "agrinexa-disposable-live-tests"


def validate_database_identity(
    database: str | None,
    revision: str | None,
    has_postgis: bool,
    marker: str | None,
) -> None:
    if database not in SAFE_DATABASES:
        raise RuntimeError("Refusing live test writes: database is not an approved disposable test database")
    if marker != DISPOSABLE_DATABASE_MARKER:
        raise RuntimeError("Refusing live test writes: database is not marked disposable")
    if revision != REQUIRED_REVISION:
        raise RuntimeError("Refusing live test writes: migration 0007 is not applied")
    if not has_postgis:
        raise RuntimeError("Refusing live test writes: PostGIS extension is unavailable")


def create_guarded_test_engine(url: str, **options):
    try:
        parsed_url = make_url(url)
    except ArgumentError:
        parsed_url = None
    if parsed_url is None:
        raise RuntimeError("Refusing live test writes: database URL is invalid")
    database = parsed_url.database
    if database not in SAFE_DATABASES:
        raise RuntimeError("Refusing live test writes: URL does not target an approved disposable test database")

    options.setdefault("hide_parameters", True)
    engine = create_engine(parsed_url, **options)
    event.listen(engine, "do_connect", safe_do_connect)

    @event.listens_for(engine, "connect")
    def verify_database(dbapi_connection, _connection_record):
        cursor = dbapi_connection.cursor()
        try:
            cursor.execute("""
                SELECT current_database(),
                       (SELECT version_num FROM public.alembic_version),
                       EXISTS (SELECT 1 FROM pg_catalog.pg_extension WHERE extname='postgis'),
                       (SELECT shobj_description(oid, 'pg_database')
                        FROM pg_catalog.pg_database
                        WHERE datname = current_database())
            """)
            state = cursor.fetchone()
            if state is None:
                raise RuntimeError("Refusing live test writes: database identity query returned no result")
            validate_database_identity(*state)
        except Exception:
            dbapi_connection.rollback()
            raise
        finally:
            cursor.close()
        dbapi_connection.rollback()

    return engine
