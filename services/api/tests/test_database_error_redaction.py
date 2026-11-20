import asyncio
import traceback

import pytest
from sqlalchemy import create_engine, event
from sqlalchemy.exc import ArgumentError, OperationalError
from sqlalchemy.pool import NullPool

from app import database
from app.main import database_unavailable


def test_engine_hides_parameters_and_accepts_postgresql_url(monkeypatch):
    database.make_engine.cache_clear()
    monkeypatch.setenv(
        "DATABASE_URL",
        "postgresql+psycopg://synthetic_user:synthetic_password@localhost/agrinexa_uat_test",
    )
    try:
        engine = database.make_engine()
        assert engine.hide_parameters is True
        assert "synthetic_password" not in repr(engine.url)
    finally:
        database.make_engine.cache_clear()


def test_malformed_url_errors_do_not_echo_connection_details(monkeypatch):
    marker = "synthetic_user synthetic_password postgresql://synthetic.invalid/uat"
    database.make_engine.cache_clear()
    monkeypatch.setenv("DATABASE_URL", "malformed synthetic URL")

    def reject_url(_url):
        raise ArgumentError(marker)

    monkeypatch.setattr(database, "make_url", reject_url)
    try:
        with pytest.raises(database.DatabaseConfigurationError) as caught:
            database.make_engine()
    finally:
        database.make_engine.cache_clear()

    rendered = "".join(traceback.format_exception(caught.value))
    assert marker not in str(caught.value)
    assert marker not in rendered
    assert caught.value.__context__ is None


def test_driver_connection_errors_are_redacted_from_exception_and_logs(caplog):
    marker = "synthetic_user synthetic_password postgresql://synthetic.invalid/uat"

    def fail_connect(*_args, **_kwargs):
        raise OSError(marker)

    with caplog.at_level("ERROR", logger=database.__name__):
        with pytest.raises(database.DatabaseConnectionError) as caught:
            database._safe_connect(fail_connect)

    rendered = "".join(traceback.format_exception(caught.value))
    assert marker not in str(caught.value)
    assert marker not in rendered
    assert marker not in caplog.text
    assert caught.value.__context__ is None
    assert "OSError" in caplog.text


def test_sqlalchemy_pool_logs_only_sanitized_connection_error(monkeypatch, caplog):
    marker = "synthetic_user synthetic_password postgresql://synthetic.invalid/uat"
    engine = create_engine("sqlite+pysqlite://", poolclass=NullPool, hide_parameters=True)

    def fail_connect(*_args, **_kwargs):
        raise OSError(marker)

    monkeypatch.setattr(engine.dialect, "connect", fail_connect)
    event.listen(engine, "do_connect", database.safe_do_connect)
    try:
        with caplog.at_level("ERROR"):
            with pytest.raises(Exception) as caught:
                engine.connect()
        rendered = "".join(traceback.format_exception(caught.value))
        assert marker not in str(caught.value)
        assert marker not in rendered
        assert marker not in caplog.text
    finally:
        engine.dispose()


def test_http_database_errors_return_generic_response_and_safe_log(caplog):
    marker = "synthetic_user synthetic_password postgresql://synthetic.invalid/uat"
    error = OperationalError("SELECT :password", {"password": marker}, OSError(marker))

    with caplog.at_level("ERROR", logger="app.main"):
        response = asyncio.run(database_unavailable(None, error))

    assert response.status_code == 503
    assert marker not in response.body.decode("utf-8")
    assert marker not in caplog.text
    assert "OperationalError" in caplog.text
