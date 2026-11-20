# GAINT AgriNexa AI — UAT role and live-test operations

**Status:** REVIEW ONLY. NOT EXECUTED. Do not run the SQL procedures without independent review and explicit approval.

## Database boundaries

- `agrinexa`: protected application database. Never use for UAT integration writes.
- `agrinexa_uat_test`: disposable UAT runtime database, separate from the live-test runner.
- `agrinexa_test`: the **only** approved database for guarded live PostGIS integration tests.
- `tests/db_safety.py` requires `SAFE_DATABASES = frozenset({"agrinexa_test"})`, the marker `agrinexa-disposable-live-tests`, PostGIS, and migration `0007_farmer_parcel_ownership`.
- The disposable marker must be checked through `shobj_description` against the connected database, not inferred from a filename or URL alone.

## Review-only procedures

1. Review `docs/uat-runtime-role-procedure.sql` for the `agrinexa_uat_runtime` role. Confirm all existing effective privileges, database connectivity, and application schema requirements before any execution.
2. Review `docs/uat-test-runner-role-procedure.sql` for `agrinexa_uat_test_runner`. Confirm the disposable marker, schema, table inventory, absence of application records, and PostGIS function signatures.
3. Keep runtime and test-runner roles separate. Do not grant membership between them or provide access to the protected `agrinexa` database.
4. Do not copy credentials from a live `.env` file. The `.env.example` file contains placeholders only.
5. Neither procedure has been executed as part of preparing these artifacts. No password has been changed.

## Guarded live integration tests

Only run these tests after explicitly configuring a newly provisioned disposable `agrinexa_test` database and validating the safety guard. Do not remove, mock, or bypass `create_guarded_test_engine`.

- `test_postgis_integration.py::test_postgis_parcel_roundtrip`
- `test_scim_job_live.py::test_scim_job_migration_applied`
- `test_scim_job_live.py::test_scim_job_lifecycle_roundtrip`
- `test_scim_claim_concurrency_live.py::test_two_connections_cannot_claim_same_job`
- `test_scim_staged_e2e_live.py::test_offline_staged_scene_end_to_end`

Each live test must use `AGRINEXA_TEST_DATABASE_URL` targeting only `agrinexa_test`; the URL alone is insufficient without the database marker and migration checks. Use unique full UUID fixture keys. Destructive cleanup must be limited to records created by that test, and should never remove existing application records.

## Validation

Run from `services/api`:

```powershell
python -m pytest tests/test_uat_role_procedure_contract.py tests/test_uat_test_runner_contract.py -q --tb=short
python -m pytest tests -q --tb=short
```

A passing contract test checks documented patterns; it does **not** verify that PostgreSQL grants are safe or that the SQL scripts have been executed. Obtain DBA review before any role provisioning. Skipped integration tests require separate verification and sign-off.
