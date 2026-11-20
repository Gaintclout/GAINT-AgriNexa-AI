# M21 Eight-Agent Integration UAT and Production Readiness

Verification date: 2026-11-20 (Asia/Calcutta)

## Decision

**Overall platform: BLOCKED for production acceptance.** Six agents pass for their explicitly restricted scopes. Market remains blocked by the missing project-owned OGD credential, immutable real capture, and human approval. Scheme remains blocked by the missing authoritative, policy-reviewed and human-approved catalogue. No dataset was self-approved and no production system was accessed.

## Environment and infrastructure

- Python backend: project `.venv`; FastAPI and PostgreSQL/PostGIS tests executed from the repository.
- Frontend: installed project dependencies; Vite production build completed.
- Playwright: `@playwright/test` 1.65.0; required Chromium revision 1254 (Chrome for Testing 158.0.8127.18).
- Browser restoration: the default user cache was inaccessible and did not contain the required executable. Chromium, headless shell, FFmpeg and Winldd were installed into `apps/web/.playwright-browsers`. All three project Playwright configs now default to that workspace cache while respecting an explicit `PLAYWRIGHT_BROWSERS_PATH` override.
- Disposable database: PostgreSQL 17 cluster bound only to `127.0.0.1:55432`; exact databases `agrinexa_agent_audit_test` and `agrinexa_test`; PostGIS enabled only in the latter. Guarded names, port, migration revision and disposable-database comment were verified by the tests. Port 5432 was not accessed.
- The cluster and all ephemeral UAT users/data were removed after verification. The restored project browser cache was retained.
- The inherited machine `PROJ_LIB` points at PostgreSQL/PostGIS's incompatible PROJ database. It was removed only from test-process environments so Rasterio used its packaged compatible database. No application behavior was changed.

## Previously skipped backend tests

All 15 former skips were investigated and executed.

| Tests | Count | Original reason | Isolated dependency and outcome |
|---|---:|---|---|
| Audit migration/legacy/append-only governance | 6 | Dedicated audit database absent | `agrinexa_agent_audit_test` on loopback 55432; PASS |
| Audit insert and mutation/truncate guards | 4 | Dedicated audit database absent | Same guarded database; PASS |
| PostGIS parcel round trip | 1 | Disposable PostGIS database absent | Guarded `agrinexa_test`; PASS |
| SCIM claim concurrency | 1 | Disposable PostGIS database absent | Same database; PASS |
| SCIM job persistence/rejection | 2 | Disposable PostGIS database absent | Same database; PASS |
| SCIM staged end-to-end | 1 | Disposable PostGIS database absent | Same database; PASS |

Result: **15 passed, 0 failed, 0 skipped**. A single combined all-tests process is intentionally incompatible with `test_no_live_database_url_in_environment`, which asserts that Milestone 13 isolated security tests run without live URLs. Therefore the correct complete execution is the non-live suite plus the separately guarded live suite, not weakening that assertion.

## Agent readiness matrix

| Agent | Classification | M21 evidence and scope |
|---|---|---|
| Intake | PASS | Real browser → FastAPI → disposable PostgreSQL preview returned normalized crop/season and the owned parcel; correlated append-only audit committed. Read-only approved preview scope only. |
| Profile | PASS | Same real workflow produced the complete parcel-backed profile with ownership enforcement and correlated audit; generated profile remains intentionally non-persistent. |
| Weather | PASS | One controlled read-only existing-client request for Hyderabad returned Open-Meteo, forecast date 2026-11-20, correct coordinates, `advisory_only=true`, `persisted=false`; provider failures remain sanitized. Pass is at verification time, not an SLA. |
| Crop Advisory | PASS | Full regression verifies conservative deterministic advice, supported input validation, advisory boundaries and unsupported-case handling. No model-generated unsupported agronomy or external action. |
| Market | BLOCKED | Adapter/resource identity, mapping, exact market filtering, provenance, units, duplicates, freshness, missing data and approved-fixture runtime pass. No project OGD key, real capture, or human-approved snapshot. |
| Scheme | BLOCKED | Contract, effective/geographic screening, documents/source evidence, human-review outcomes, missing data and approved-fixture runtime pass. No policy-reviewed authoritative catalogue or human approval. |
| Escalation | PASS | Authorized live review produced `human_review_required=true`, `external_action_performed=false`, and a committed audit row with correlation. Fail-closed audit behavior and role restrictions pass. No dispatch. |
| Learning | PASS | Authorized live review committed correlated audit; `training_performed=false`, `model_updated=false`, `feedback_persisted=false`. Admin/ML Team restriction and fail-closed audit behavior pass. |

## Market official-source status

- Official OGD catalogue: `https://www.data.gov.in/catalog/current-daily-price-various-commodities-various-markets-mandi`.
- Government resource ID: `9ef84268-d588-465a-a308-a864a43d0070`.
- Publisher: Directorate of Marketing and Inspection, Department of Agriculture and Farmers Welfare, Ministry of Agriculture and Farmers Welfare.
- License context: NDSAP / resource metadata and Government Open Data License - India; attribution and non-endorsement requirements remain.
- M20 adapter validation remains intact for resource identity, state, district, market, source commodity, normalized supported commodity, variety, grade, arrival date, min/max/modal prices, `INR/quintal`, response publication time, retrieval time, duplicates and date-only precision.
- Environment inspection found no approved OGD/data.gov.in/AGMARKNET credential variable. No public third-party key, scraping, or authentication bypass was used.

Market approval status: no real draft, validated or approved artifact exists; no version/hash/approval actor can truthfully be reported. Synthetic approved artifacts are confined to technical tests and never establish production readiness.

## Scheme authoritative-source status

PM-KISAN, the revised PM-KISAN guidelines, Telangana TGMIP, Telangana MeeSeva agriculture services, and official Telangana scheme inventories were reassessed. The evidence continues to show useful authority, geography, exclusions or application information, but not a single revision-controlled catalogue adequate for definitive current eligibility across the intended Telangana deployment.

`docs/data/M21_SCHEME_HUMAN_REVIEW_CANDIDATES.json` prepares three non-runtime evidence candidates for a policy reviewer. It deliberately preserves missing revision dates, effective dates and document/rule questions as nulls or review questions. It is not a Scheme v2 catalogue, cannot be loaded by the agent, and was not submitted or approved.

## Dataset governance verification

The complete technical lifecycle passed with labeled fixtures:

- Immutable draft → validated → approved artifacts and separate rejected artifacts.
- Canonical SHA-256 and tamper rejection.
- Dataset/source/license/unit/import/approval provenance.
- Composite Market observation and Scheme identifier duplicate rejection.
- Admin-only approval/rejection, actor/role/time/decision identifier, and substantive rejection reason.
- Deterministic re-import and refusal to overwrite conflicting content.
- Runtime rejection of draft, validated, rejected, tampered, wrong-kind and non-approved-directory v2 data.
- Exact configured path permits controlled selection/rollback to any previously approved immutable version.

Automated validation never approves a dataset. M21 performed no authoritative-data approval.

## Browser and end-to-end evidence

| Browser scope | Result |
|---|---|
| Fixture-backed Chromium regression | **9 passed**: registration, duplicate handling, login/logout/expiry, sanitized error, parcel isolation, offline drafts, idempotent sync, officer reviews/audit history, responsive layouts, eight Agent Metadata cards and unauthorized/expired access. |
| Real FastAPI Agent Metadata | **2 passed**: Admin, GIS Operator and ML Team saw eight cards and role-appropriate workspaces; Farmer navigation denied. |
| Real Intake/Profile workflow | **1 passed**: authenticated browser request returned HTTP 200 and committed one independently verified audit event. |
| Browser errors/network failures | None asserted in the passing scenarios. |

The Playwright assertions completed successfully. On this Windows runner, Vite's child process did not exit after test completion, so the orchestration session was interrupted only after all pass results were emitted. This is a test-runner cleanup limitation, not an application assertion failure.

## Test results

| Suite | Passed | Failed | Skipped | Result |
|---|---:|---:|---:|---|
| Complete non-live backend regression | 1,069 | 0 | 15 | PASS; 15 were then executed separately |
| Guarded PostgreSQL/PostGIS live suite | 15 | 0 | 0 | PASS |
| Applicable backend total across required isolation modes | **1,084** | **0** | **0** | PASS |
| One-process experiment with live URLs | 1,083 | 1 | 0 | Expected isolation-contract conflict; not the valid execution mode |
| Frontend Node tests | 41 | 0 | 0 | PASS |
| Fixture Chromium | 9 | 0 | 0 | PASS |
| Real Agent Metadata Chromium | 2 | 0 | 0 | PASS |
| Real Intake/Profile Chromium | 1 | 0 | 0 | PASS |
| Frontend production build | n/a | 0 | 0 | PASS; 1,657 modules transformed |
| Controlled live Weather request | 1 | 0 | 0 | PASS at verification time |

The pytest cache warning is caused by denied writes to `services/api/.pytest_cache`; explicit workspace basetemp directories were used and test execution was unaffected.

## Security and governance

- Dedicated router authentication and role restrictions: PASS.
- Account active/role re-checks: PASS.
- Generic execution disabled for all eight agents: PASS.
- Audit inserts persistent and append-only; update/delete/truncate rejected: PASS on PostgreSQL.
- Audit storage failures fail closed: PASS.
- Intake/Profile parcel ownership and non-disclosing isolation: PASS.
- Dataset approval bypass and unapproved authoritative runtime: rejected.
- External escalation action: disabled.
- Automatic learning, feedback persistence, model training/update/deployment: disabled.
- No production/shared database, production source configuration, password, or deployed service changed.

## Defects resolved

1. **Missing Playwright runtime** — installed revision 1254 to a workspace cache and made all Playwright configs use it by default.
2. **Fifteen unexecuted guarded live tests** — provisioned exact disposable databases, executed all tests, and removed the cluster afterward.
3. **Scheme-review handoff gap** — added a clearly non-authoritative evidence-candidate artifact with unresolved fields and reviewer questions; it cannot enter runtime accidentally.

Remaining test-infrastructure limitations are the inherited system `PROJ_LIB`, denied local pytest cache, and Vite child-process cleanup after Playwright completion. None changed application results.

## Remaining blockers and next milestone

1. Obtain a project-owned data.gov.in API key, confirm official limits, capture/checksum a bounded OGD response, validate it, and obtain explicit Admin/data-owner approval.
2. Assign a Telangana scheme policy owner to resolve candidate questions against current notifications/guidelines and explicitly approve a canonical v2 catalogue.
3. Run source-record-to-API-to-browser comparisons using those approved real datasets.
4. Establish operational refresh/expiry ownership, credential storage, approved-directory filesystem permissions, and provider monitoring before deployment review.
5. Optionally stabilize the Windows Playwright web-server teardown and project test environment variables for repeatable CI.

Recommended next milestone: **M22 approved authoritative dataset onboarding and source-to-browser acceptance**. Until both mandatory datasets receive explicit human approval, the complete platform must remain **BLOCKED**.
