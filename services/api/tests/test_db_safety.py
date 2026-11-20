import pytest
from sqlalchemy.exc import ArgumentError
from db_safety import (
    DISPOSABLE_DATABASE_MARKER,
    REQUIRED_REVISION,
    create_guarded_test_engine,
    validate_database_identity,
)


def test_database_identity_requires_allowlisted_name_revision_and_postgis():
    assert validate_database_identity(
        "agrinexa_test", REQUIRED_REVISION, True, DISPOSABLE_DATABASE_MARKER
    ) is None
    with pytest.raises(RuntimeError, match="approved disposable"):
        validate_database_identity("agrinexa", REQUIRED_REVISION, True, DISPOSABLE_DATABASE_MARKER)
    with pytest.raises(RuntimeError, match="approved disposable"):
        validate_database_identity("agrinexa_uat_test", REQUIRED_REVISION, True, DISPOSABLE_DATABASE_MARKER)
    with pytest.raises(RuntimeError, match="marked disposable"):
        validate_database_identity("agrinexa_test", REQUIRED_REVISION, True, None)
    with pytest.raises(RuntimeError, match="marked disposable"):
        validate_database_identity(
            "agrinexa_test", REQUIRED_REVISION, True, "not-a-disposable-database"
        )
    with pytest.raises(RuntimeError, match="migration 0007"):
        validate_database_identity("agrinexa_test", "0006_field_verification", True, DISPOSABLE_DATABASE_MARKER)
    with pytest.raises(RuntimeError, match="PostGIS"):
        validate_database_identity("agrinexa_test", REQUIRED_REVISION, False, DISPOSABLE_DATABASE_MARKER)


def test_guarded_engine_rejects_protected_database_before_connecting():
    with pytest.raises(RuntimeError, match="approved disposable"):
        create_guarded_test_engine("postgresql://localhost/agrinexa")
    with pytest.raises(RuntimeError, match="approved disposable"):
        create_guarded_test_engine("postgresql://localhost/agrinexa_uat_test")


def test_guarded_engine_hides_parameters_without_connecting():
    engine = create_guarded_test_engine(
        "postgresql+psycopg://synthetic_user:synthetic_password@localhost/agrinexa_test"
    )
    try:
        assert engine.hide_parameters is True
    finally:
        engine.dispose()


def test_invalid_database_url_error_does_not_echo_url(monkeypatch):
    import db_safety

    marker = "synthetic_user synthetic_password postgresql://synthetic.invalid/uat"

    def reject_url(_url):
        raise ArgumentError(marker)

    monkeypatch.setattr(db_safety, "make_url", reject_url)

    with pytest.raises(RuntimeError, match="URL is invalid") as caught:
        create_guarded_test_engine(f"malformed-{marker}")

    assert marker not in str(caught.value)
    assert caught.value.__context__ is None
