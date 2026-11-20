import ast
from pathlib import Path


MIGRATION = (
    Path(__file__).resolve().parents[1]
    / "migrations" / "versions" / "0012_agent_audit_governance.py"
)


def test_migration_is_new_revision_and_parses():
    source = MIGRATION.read_text()
    tree = ast.parse(source)
    values = {}
    for node in tree.body:
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id in {"revision", "down_revision"}:
                    values[target.id] = ast.literal_eval(node.value)
    assert values == {
        "revision": "0012_agent_audit_governance",
        "down_revision": "0011_persistent_auth_sessions",
    }


def test_migration_preserves_existing_rows_and_guards():
    source = MIGRATION.read_text().upper()
    assert "DROP TABLE" not in source
    assert "TRUNCATE" not in source
    assert "DELETE FROM" not in source
    assert "CORRELATION_ID" in source
    assert "SUBJECT_ID" in source
    assert "IX_AGENT_AUDIT_CORRELATION" in source


def test_downgrade_requires_explicit_approval():
    assert "raise RuntimeError(" in MIGRATION.read_text()
