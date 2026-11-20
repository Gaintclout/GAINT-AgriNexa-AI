"""PostgreSQL/PostGIS database configuration; no implicit schema changes."""
import logging
import os
from functools import lru_cache
from sqlalchemy import create_engine, event
from sqlalchemy.engine import make_url
from sqlalchemy.exc import ArgumentError, NoSuchModuleError
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

LOG = logging.getLogger(__name__)


class DatabaseConfigurationError(RuntimeError):
    pass


class DatabaseConnectionError(RuntimeError):
    pass


def _safe_connect(connector, *args, **kwargs):
    try:
        return connector(*args, **kwargs)
    except Exception as exc:
        error_type = type(exc).__name__
    LOG.error("Database connection failed (driver error type: %s)", error_type)
    raise DatabaseConnectionError("Database connection failed")


def safe_do_connect(dialect, _connection_record, cargs, cparams):
    return _safe_connect(dialect.connect, *cargs, **cparams)


class Base(DeclarativeBase):
    pass


@lru_cache(maxsize=1)
def make_engine():
    url = os.environ.get("DATABASE_URL", "")
    try:
        parsed_url = make_url(url)
    except ArgumentError:
        parsed_url = None
    if parsed_url is None:
        raise DatabaseConfigurationError("DATABASE_URL is invalid")
    if parsed_url.drivername not in ("postgresql", "postgresql+psycopg"):
        raise DatabaseConfigurationError("DATABASE_URL must be a PostgreSQL connection string")
    try:
        engine = create_engine(parsed_url, pool_pre_ping=True, hide_parameters=True)
    except (ArgumentError, NoSuchModuleError):
        engine = None
    if engine is None:
        raise DatabaseConfigurationError("DATABASE_URL is invalid or uses an unsupported driver")
    event.listen(engine, "do_connect", safe_do_connect)
    return engine


def session_factory():
    return sessionmaker(bind=make_engine(), autoflush=False, expire_on_commit=False)


def get_db():
    factory = session_factory()
    with factory() as session:
        yield session
