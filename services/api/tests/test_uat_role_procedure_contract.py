import re
from pathlib import Path


PROCEDURE = Path(__file__).parents[3] / "docs" / "uat-runtime-role-procedure.sql"
API_ENV_EXAMPLE = Path(__file__).parents[1] / ".env.example"


def test_uat_role_procedure_is_scoped_and_least_privilege():
    sql = PROCEDURE.read_text(encoding="utf-8").lower()

    assert "review only. not executed" in sql
    assert "current_database() <> 'agrinexa_uat_test'" in sql
    assert "agrinexa_uat_runtime" in sql
    assert "nologin" in sql
    assert "has_database_privilege" in sql
    assert "datname <> 'agrinexa_uat_test'" in sql
    assert "has_schema_privilege" in sql
    assert "has_table_privilege" in sql
    assert "has_sequence_privilege" in sql
    assert "public.alembic_version" in sql
    for privilege in ("nosuperuser", "nocreatedb", "nocreaterole", "noreplication", "nobypassrls", "noinherit"):
        assert privilege in sql
    assert "grant all" not in sql
    assert "grant delete" not in sql
    assert "grant truncate" not in sql
    assert "grant create" not in sql
    assert "\\password agrinexa_uat_runtime" in sql
    assert sql.index("\\password agrinexa_uat_runtime") < sql.index("alter role agrinexa_uat_runtime login")


def test_role_procedure_never_targets_protected_database_or_existing_role_changes():
    sql = PROCEDURE.read_text(encoding="utf-8").lower()

    assert "on database agrinexa " not in sql
    assert re.findall(r"\balter\s+role\s+([a-z0-9_]+)", sql) == ["agrinexa_uat_runtime"]
    assert "drop role" not in sql


def test_tracked_environment_example_uses_placeholders_and_disposable_database():
    example = API_ENV_EXAMPLE.read_text(encoding="utf-8").lower()

    assert "replace_with_local_user:replace_with_local_password" in example
    assert "/agrinexa_uat_test" in example
    assert "/agrinexa\n" not in example
