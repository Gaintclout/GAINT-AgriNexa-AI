import ast
import re
from pathlib import Path


ROOT = Path(__file__).parents[3]
API_TESTS = ROOT / "services" / "api" / "tests"
RUNNER_PROCEDURE = ROOT / "docs" / "uat-test-runner-role-procedure.sql"
RUNTIME_PROCEDURE = ROOT / "docs" / "uat-runtime-role-procedure.sql"
OPERATIONS_DOC = ROOT / "docs" / "uat-runtime-role-operations.md"
LIVE_TESTS = (
    ("test_postgis_integration.py", "test_postgis_parcel_roundtrip"),
    ("test_scim_job_live.py", "test_scim_job_migration_applied"),
    ("test_scim_job_live.py", "test_scim_job_lifecycle_roundtrip"),
    ("test_scim_claim_concurrency_live.py", "test_two_connections_cannot_claim_same_job"),
    ("test_scim_staged_e2e_live.py", "test_offline_staged_scene_end_to_end"),
)


def test_runner_role_is_separate_and_disposable_database_only():
    sql = RUNNER_PROCEDURE.read_text(encoding="utf-8").lower()

    assert "current_database() <> 'agrinexa_test'" in sql
    assert "agrinexa-disposable-live-tests" in sql
    assert "disposable test database contains application records" in sql
    assert "create role agrinexa_uat_test_runner" in sql
    assert "nologin" in sql
    assert "noinherit" in sql
    assert "grant connect on database agrinexa_test" in sql
    assert "grant connect on database agrinexa_uat_test" not in sql
    assert "grant connect on database agrinexa " not in sql
    assert "public.alembic_version" in sql
    assert "has_function_privilege" in sql
    for function in (
        "st_asgeojson",
        "st_geomfromgeojson",
        "st_geomfromtext",
        "st_intersects",
        "st_isvalid",
        "st_makeenvelope",
        "st_multi",
        "st_setsrid",
    ):
        assert function in sql
    assert "pg_has_role(" in sql
    assert "'agrinexa_uat_runtime', 'agrinexa', 'connect'" in sql
    assert "'agrinexa_uat_test_runner', 'agrinexa', 'connect'" in sql
    assert "'agrinexa_uat_runtime', 'agrinexa_test', 'connect'" in sql
    assert "'agrinexa_uat_test_runner', 'agrinexa_uat_test', 'connect'" in sql
    assert re.search(r"grant select, insert, delete on table\s+public\.states", sql)
    assert "grant select, insert, update, delete on table" in sql
    assert "grant create" not in sql
    assert "grant truncate" not in sql
    assert "alter table" not in sql
    assert "create table" not in sql
    assert "\\password agrinexa_uat_test_runner" in sql
    assert sql.index("\\password agrinexa_uat_test_runner") < sql.index(
        "alter role agrinexa_uat_test_runner login"
    )


def test_runtime_role_procedure_remains_separate_and_has_no_test_runner_grants():
    runtime_sql = RUNTIME_PROCEDURE.read_text(encoding="utf-8").lower()
    runner_sql = RUNNER_PROCEDURE.read_text(encoding="utf-8").lower()

    assert "grant agrinexa_uat_test_runner" not in runtime_sql
    assert "grant agrinexa_uat_runtime" not in runner_sql
    assert "pg_has_role(" in runner_sql
    assert "agrinexa_uat_runtime', 'agrinexa_uat_test_runner', 'member'" in runner_sql
    assert "agrinexa_uat_test_runner', 'agrinexa_uat_runtime', 'member'" in runner_sql


def test_all_live_postgis_tests_require_the_disposable_database_guard():
    db_safety = (API_TESTS / "db_safety.py").read_text(encoding="utf-8")
    assert 'SAFE_DATABASES = frozenset({"agrinexa_test"})' in db_safety
    assert 'DISPOSABLE_DATABASE_MARKER = "agrinexa-disposable-live-tests"' in db_safety
    assert "shobj_description" in db_safety

    operations = OPERATIONS_DOC.read_text(encoding="utf-8")
    for filename, test_name in LIVE_TESTS:
        source = (API_TESTS / filename).read_text(encoding="utf-8")
        assert "create_guarded_test_engine" in source
        assert "AGRINEXA_TEST_DATABASE_URL" in source
        assert "agrinexa_uat_test" not in source
        assert "create_all(" not in source
        assert "drop_all(" not in source
        assert "CREATE TABLE" not in source.upper()
        assert "ALTER TABLE" not in source.upper()
        assert test_name in operations


def test_destructive_cleanup_is_fixture_scoped_and_uses_full_uuid_keys():
    deleting_tests = (
        "test_scim_claim_concurrency_live.py",
        "test_scim_staged_e2e_live.py",
    )
    delete_count = 0

    for filename in deleting_tests:
        source = (API_TESTS / filename).read_text(encoding="utf-8")
        tree = ast.parse(source)
        parents = {
            child: node
            for node in ast.walk(tree)
            for child in ast.iter_child_nodes(node)
        }
        deletes = [
            node
            for node in ast.walk(tree)
            if isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id == "delete"
        ]
        assert deletes
        delete_count += len(deletes)
        for deletion in deletes:
            where_attribute = parents[deletion]
            assert isinstance(where_attribute, ast.Attribute)
            assert where_attribute.attr == "where"
            scoped_call = parents[where_attribute]
            assert isinstance(scoped_call, ast.Call)
            assert scoped_call.args
            assert any(
                isinstance(node, ast.Compare)
                and any(isinstance(op, ast.Eq) for op in node.ops)
                for node in ast.walk(scoped_call.args[0])
            )
        assert "key = uuid4().hex" in source
        assert "uuid4().hex[:12]" not in source

    assert delete_count == 13
