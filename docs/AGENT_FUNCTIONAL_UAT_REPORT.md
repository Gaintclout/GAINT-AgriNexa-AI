# GAINT AgriNexa AI — Agent Functional UAT Report

Date: 2026-11-19  
Environment: local development workspace, Windows, isolated automated UAT  
Overall decision: **PASS for M18 audit governance and Weather verification; BLOCKED for full product production acceptance pending authoritative Market and Scheme datasets**

## 1. Environment readiness

| Item | Status | Evidence |
|---|---|---|
| FastAPI application and OpenAPI schema | PASS | Application imports and isolated `TestClient` requests execute successfully. |
| Agent-related API operations | PASS | 11 operations exist below `/api/v1/agents`; `/api/v1/metadata` is the twelfth agent-related operation. |
| Python dependencies | PASS | Backend suites execute with the workspace virtual environment. |
| Node dependencies | PASS | Frontend unit tests and Vite production build execute. |
| Application database | PASS for isolated UAT | A workspace-owned PostgreSQL 17 cluster was created on `127.0.0.1:55432`, fully migrated, and kept separate from the existing port-5432 service. No shared or production database was accessed. |
| Persistent audit migrations | PASS | Static schema/migration and isolated sink tests pass. |
| Live PostgreSQL audit persistence | PASS | All 9 guarded live tests ran against `agrinexa_agent_audit_test`; schema, inserts, rollback, and update/delete/truncate guards passed. |
| Market data | BLOCKED | `AGRINEXA_MARKET_SNAPSHOT_PATH` is not configured. |
| Scheme data | BLOCKED | `AGRINEXA_SCHEME_CATALOGUE_PATH` is not configured. |
| Weather provider | NOT TESTED | No live Open-Meteo call was made. HTTP UAT uses an explicitly declared provider fixture. |
| Browser UAT | PASS | Pinned Playwright Chromium installed; 9 fixture-backed and 2 real FastAPI/PostgreSQL Agent Metadata scenarios passed. |

No credentials, tokens, password values, database URLs, or personal information were printed. No production or shared database was used.

## 2. API contract inventory

| Method | Route | Verification |
|---|---|---|
| GET | `/api/v1/metadata` | PASS |
| GET | `/api/v1/agents` | PASS |
| GET | `/api/v1/agents/{agent_id}` | PASS |
| POST | `/api/v1/agents/{agent_id}/execute` | PASS — rejects all eight agents |
| GET | `/api/v1/agents/intake-profile/availability` | PASS |
| POST | `/api/v1/agents/intake-profile/preview` | PASS through authenticated Chromium, real FastAPI, disposable PostgreSQL parcel data, and committed append-only audit persistence |
| POST | `/api/v1/agents/weather/forecast` | PASS with explicit fixture; live provider NOT TESTED |
| POST | `/api/v1/agents/crop-advisory/generate` | PASS |
| POST | `/api/v1/agents/market/prices` | PASS for unconfigured-source behavior |
| POST | `/api/v1/agents/schemes/screen` | PASS for unconfigured-source behavior |
| POST | `/api/v1/agents/escalation/screen` | PASS |
| POST | `/api/v1/agents/learning/review` | PASS |

## 3. Agent UAT results

### INTAKE — PASS for approved preview scope

- Verified implementation: strict request model, whitespace normalization, length limits, extra-field rejection, authenticated preview route, and explicit approval gate.
- Data: authorized parcel registry and assigned Farmer account.
- Authorization: Admin, GIS Operator, and ML Team. Anonymous and Farmer HTTP access is rejected.
- Isolation: Farmer parcel access uses ownership checks and returns 404 for another Farmer's parcel.
- Audit: allowed and denied attempts build minimal audit events; audit delivery must complete before a result is returned.
- Functional result: validation, normalization, authorization, isolation, and fail-closed behavior PASS in automated tests.
- M17 evidence: a valid database-backed preview completed through Chromium and real FastAPI with the correct Farmer-owned parcel, followed by a committed audit row.
- Duplicate handling: not implemented as an Intake concept; parcel identity is resolved from the registry rather than created here.
- Production readiness: PASS for the explicitly approved read-only preview scope in a migrated, monitored environment; full product acceptance remains blocked by unrelated data-source and audit limitations.

### PROFILE — PASS for approved preview scope

- Verified implementation: deterministic completeness calculation using Farmer ID, parcel ID, crop, and season. Missing values are reported rather than inferred.
- Authorization and isolation: shared with Intake; ownership and active-account checks pass.
- Audit: shared mandatory persistent audit path; audit-storage failure returns HTTP 503.
- Functional result: profile construction and missing-field tests PASS.
- M17 evidence: live persistent audit commit and database-backed success are verified; the generated profile remains intentionally non-persistent.
- Production readiness: PASS for the explicitly approved deterministic preview scope.

### WEATHER — BLOCKED

- Verified implementation: coordinate validation, bounded provider response read, date parsing, missing-measurement rejection, and deterministic heat/rain/wind risk thresholds.
- Provenance: response identifies Open-Meteo. UAT success response was fixture-backed and is not evidence of live provider availability.
- Authorization: Admin, GIS Operator, and ML Team; anonymous and Farmer access rejected.
- Error behavior: provider/network/format failures are sanitized to HTTP 503.
- Frontend: authenticated form, coordinate validation, loading, error, metric, risk, and advisory states are implemented.
- Blocker: live Open-Meteo connectivity, response behavior, rate limits, and operational SLA were not tested.
- Production readiness: BLOCKED pending controlled live-provider verification.

### CROP_ADVISORY — PASS for implemented advisory scope

- Verified implementation: deterministic rules for rice, wheat, maize, cotton, groundnut, and tomato across establishment, vegetative, flowering, and harvest stages.
- Evidence: outputs label general crop guidance, growth-stage rules, and optional forecast thresholds.
- Validation: unsupported crops/stages, extra fields, incomplete coordinate pairs, and missing coordinates for requested weather are rejected.
- Safety: no disease diagnosis, chemical prescription, autonomous action, or yield guarantee.
- Weather degradation: provider failure returns rule-only guidance with `weather_status=unavailable`; it does not invent weather.
- Frontend: authenticated form, optional weather inputs, loading/error/results, evidence labels, and disclaimer implemented.
- Production readiness: PASS only as a read-only conservative advisory; not accepted as diagnostic or prescriptive agronomy.

### MARKET — BLOCKED

- Verified implementation: schema-versioned local snapshot loader, commodity/location filtering, deterministic ordering, market identity, timestamps, price-range validation, source URL validation, freshness classification, and request limits.
- Real-data status: unavailable. No snapshot is configured and no prices are fabricated.
- HTTP UAT: returns `source_status=not_configured`, empty records, and `available=false`.
- Authorization: Admin, GIS Operator, and ML Team; anonymous and Farmer access rejected.
- Frontend: authenticated filters, loading/error/empty/results, dates, sources, and freshness display implemented.
- Blocker: no controlled snapshot, refresh ownership, provenance process, or freshness SLA.
- Production readiness: BLOCKED.

### SCHEME — BLOCKED

- Verified implementation: validated catalogue schema, unique IDs, HTTPS official URLs, verification dates, location/category/land rules, and explainable `potential_match`, `needs_review`, or `not_matched` results.
- Documents: configured document lists are displayed; missing catalogue evidence is not invented.
- Real-data status: unavailable. No catalogue is configured.
- HTTP UAT: returns `source_status=not_configured`, empty schemes, and `available=false`.
- Authorization: Admin, GIS Operator, and ML Team; anonymous and Farmer access rejected.
- Frontend: authenticated screening form, validation, empty/error/results, official-source links, and preliminary-screening warnings implemented.
- Blocker: no authoritative catalogue, refresh process, or source owner.
- Production readiness: BLOCKED.

### ESCALATION — PASS for screening scope

- Verified implementation: deterministic indicator weights, deduplication, score cap, severity boundaries, evidence-status confidence, and human-review recommendations.
- Duplicate behavior: duplicate indicators do not increase the score; verified evidence is preferred.
- Authorization: Admin, GIS Operator, and ML Team; anonymous and Farmer access rejected.
- Safety: no notifications, dispatch, official emergency assessment, or external action.
- Auditability: inputs/results are stateless and no persistent workflow audit exists. This is a remaining governance limitation, not concealed as a success.
- Frontend: authenticated evidence form, validation, loading/error/results, severity, reasons, actions, and disclaimers implemented.
- Production readiness: PASS only as a human-review prioritization aid; not an emergency system.

### LEARNING — PASS for manual review scope

- Verified implementation: deterministic feedback/evidence classification, duplicate feedback rejection, and human-review proposals.
- Authorization: Admin and ML Team only. Anonymous, Farmer, and GIS Operator access rejected; GIS workspace is hidden.
- Governance: `training_performed`, `model_updated`, `feedback_persisted`, and `external_action_performed` remain false. Human approval remains required.
- Auditability: stateless; no persistent review record exists.
- Frontend: authenticated review form, validation, loading/error/results, evidence status, and safety priority implemented.
- Production readiness: PASS only as a restricted manual review tool. It is not automatic learning or model training.

## 4. Frontend UAT

| Check | Status | Notes |
|---|---|---|
| Authenticated request mechanism | PASS | All implemented workspaces use `AuthContext.request`. |
| Route binding | PASS | Contract tests verify every workspace uses its registered dedicated route. |
| Generic execution avoidance | PASS | No workspace calls `/{agent_id}/execute`. |
| Role visibility | PASS | Governance page is restricted; Learning is hidden from GIS Operator. |
| Forms and client validation | PASS | Source inspection and automated contract tests. |
| Loading/error/empty/result states | PASS | Implemented in each applicable workspace. |
| Metadata capability distinctions | PASS | Configured execution, generic execution, route registration, runtime readiness, and learning are separate. |
| Browser interaction | PASS | Chromium ran navigation, role, expiry, metadata, isolation, and responsive scenarios. |
| Real frontend plus live backend | PASS for Agent Metadata and Intake/Profile | Vite used its same-origin proxy to real FastAPI and the disposable migrated PostgreSQL database. |

## 5. Security and audit verification

- **PASS:** generic execution is rejected for all eight agents.
- **PASS:** approval revocation blocks Intake/Profile preview.
- **PASS:** successful Intake/Profile results require audit delivery first.
- **PASS:** audit storage failure fails closed.
- **PASS:** audit events omit crop, season, and request payload details.
- **PASS:** unauthorized roles are rejected at HTTP dependency level.
- **PASS:** parcel ownership isolation and non-disclosing 404 behavior.
- **PASS:** automatic learning, training, model update, and deployment remain disabled.
- **PASS:** external source errors are sanitized.
- **PASS:** actual PostgreSQL audit inserts and append-only update/delete/truncate guards were live-tested.
- **BLOCKED:** Escalation and Learning have no persistent workflow audit records.

## 6. Test execution summary

Final M16 consolidated results:

- Backend non-live agent/security suite: **365 passed, 0 failed, 0 skipped**.
- Live PostgreSQL audit suite: **9 passed, 0 failed, 0 skipped**.
- Frontend Node tests: **41 passed, 0 failed, 0 skipped**.
- Fixture-backed browser regression: **9 passed, 0 failed, 0 skipped**.
- Real FastAPI/PostgreSQL Agent Metadata browser UAT: **2 passed, 0 failed, 0 skipped**.
- Total automated tests passed: **426**.
- Frontend production build: **PASS** (1,657 modules transformed).
- Browser runtime: **PASS** using the project-pinned Chromium installation.
- Live audit tests: **PASS** using the guarded disposable database identity.

Automated-test success is not treated as live provider, live database, or browser verification.

## 7. Defects and fixes

1. **Authenticated valid-flow HTTP coverage gap**
   - Reproduction: existing suites emphasized engine/direct-router tests and security declarations.
   - Root cause: no consolidated isolated authenticated HTTP UAT across the registered workflows.
   - Fix: added `test_agent_functional_uat_http.py` with explicit fixture/source boundaries.
   - Regression result: 9 tests passed before the final consolidated run.

2. **Stale Intake/Profile governance wording**
   - Reproduction: router comments claimed activation remained disabled while the explicit approval flag was true.
   - Root cause: pre-approval documentation remained after approval changed.
   - Fix: wording now states approval plus mandatory fail-closed audit persistence.
   - Functional behavior: unchanged.

3. **Real Uvicorn logout response failure (M16)**
   - Reproduction: browser logout reached FastAPI, but the injected response retained a `None` runtime status and Uvicorn terminated the response with a socket error.
   - Root cause: the decorator declared 204, but the handler returned the injected `Response` without explicitly setting its status.
   - Fix: set `response.status_code` to HTTP 204 before returning it.
   - Regression result: session-security tests and real browser sign-in/sign-out across Admin, GIS Operator, and ML Team pass.

4. **Expired-session browser race (M16)**
   - Reproduction: the one-second fixture token is inside the application's 60-second renewal window, so it can expire before a transient signed-in assertion renders.
   - Root cause: the test asserted an inherently racy intermediate state.
   - Fix: preserve the security assertion that the session expires and remove only the transient signed-in assertion.

5. **Live UAT same-origin configuration (M16)**
   - Reproduction: direct cross-origin Vite-to-API login was rejected by the existing origin guard.
   - Root cause: the first live-UAT configuration bypassed the supported Vite proxy architecture.
   - Fix: parameterize the development proxy target and run live UAT through a same-origin Vite proxy. Production defaults and origin checks are unchanged.

## 8. Remaining limitations and acceptance

Remaining production blockers after M16:

1. No configured Market snapshot or Scheme catalogue.
2. No controlled live Weather-provider verification.
3. No persistent Escalation or Learning review audit trail.
4. Full parcel-backed Intake/Profile execution was not browser-tested because M16 did not seed agricultural parcel data.

M16 decision: **PASS**. The PostgreSQL audit and browser-runtime blockers are resolved with isolated, disposable infrastructure. Overall product production acceptance remains **BLOCKED** by live data-source and remaining workflow-audit limitations.

## 9. Recommended next milestone

1. Add a non-sensitive request/correlation identifier to the governed audit contract and verify propagation without storing request payloads.
2. Add agent-workflow browser scenarios for 404/422/503 presentation beyond Agent Metadata.
3. Onboard controlled Market and Scheme sources with provenance, refresh ownership, and expiry policies.
4. Run a bounded non-production Open-Meteo connectivity test.
5. Define minimal persistent audit requirements for Escalation and manual Learning review before operational use.

## 10. M17 Intake/Profile real-workflow UAT

### Isolated environment and data

- Created a workspace-owned PostgreSQL 17 cluster bound only to `127.0.0.1:55432`; the guarded database name was exactly `agrinexa_agent_audit_test`.
- Verified the database identity before use and applied Alembic through `0011_persistent_auth_sessions`.
- Seeded only two disposable users (one active Admin operator and one active Farmer), one village, and one Farmer-owned parcel. Password material was randomly generated per run and was not recorded.
- The existing PostgreSQL service on port 5432 was not accessed. No shared or production record was read or changed.

### Authenticated browser execution

- Playwright Chromium authenticated through the existing login UI, opened AI Agents, selected the disposable parcel in the existing Intake/Profile workspace, and submitted the existing approved preview route.
- Actual HTTP status: `200` from `POST /api/v1/agents/intake-profile/preview`.
- Verified response values: Farmer `m17-uat-farmer`; parcel `17000000-0000-4000-8000-000000000017`; normalized crop `rice`; normalized season `kharif`; Intake `validated`; Profile `complete`; completeness `100`; village `M17-UAT-VILLAGE`; area `2.5000`; source `parcel_registry`; `persisted=false`.
- `persisted=false` correctly describes the generated profile. The governance audit is persisted independently and must commit before the response can succeed.
- Browser page errors: 0. Failed browser network requests: 0.

### Audit persistence evidence

- Exactly one audit row existed for the operation after the browser request; database totals were two users, one village, one parcel, and one audit event.
- Verified fields: unique event ID present; actor `m17-uat-admin`; role `admin`; correct parcel ID; operation `INTAKE_PROFILE`; outcome `allowed`; reason `AUTHORIZED`; timezone-aware creation timestamp present.
- The current eight-column audit schema has a unique event ID but no separate request/correlation ID column. No unsupported correlation claim is made; cross-system request correlation remains a governance limitation.
- The nine live PostgreSQL tests confirmed actual inserts plus append-only rejection of update, delete, and truncate operations.

### Negative and governance verification

- Unauthorized and Farmer-role preview access is rejected.
- Missing/invalid parcel context, unassigned parcels, inactive/deleted/non-Farmer owners, and cross-Farmer reads are rejected without disclosing another Farmer's data.
- Approval revocation prevents execution.
- Audit delivery failure prevents a successful profile result and fails closed.
- Generic agent execution remains disabled for all eight agents.
- Learning remains manual review only; automatic learning, training, model update, and deployment remain disabled.
- The permitted preview is deterministic and read-only; no profile, Farmer, village, or parcel mutation occurs.

### M17 verification results

| Suite | Passed | Failed | Skipped/blocked | Result |
|---|---:|---:|---:|---|
| Live Intake/Profile Chromium UAT | 1 | 0 | 0 | PASS |
| Focused Intake/Profile security/governance regression | 83 | 0 | 0 | PASS |
| Live PostgreSQL audit suite | 9 | 0 | 0 | PASS |
| Complete backend suite excluding separately run live audit files | 1,040 | 0 | 5 | PASS |
| Frontend Node tests | 41 | 0 | 0 | PASS |
| Fixture-backed browser regression | 9 | 0 | 0 | PASS |
| Frontend production build | n/a | 0 | 0 | PASS; 1,657 modules transformed |

The first complete-backend attempt had 24 SCIM raster failures because the machine-level `PROJ_LIB` referenced PostgreSQL/PostGIS's incompatible PROJ database. Removing that inherited variable for the test process allowed Rasterio to use its packaged database; the repeat passed 1,040 tests. An earlier focused-suite invocation from the wrong working directory produced eight collection errors and ran zero tests. Neither invocation is counted as a passing run.

### M17 files and disposition

- Added `services/api/tests/seed_intake_profile_uat.py` with exact host/port/database guards and minimum-data seeding.
- Added `services/api/tests/verify_intake_profile_uat.py` for independent, read-only committed-row verification.
- Added `apps/web/playwright.intake-live.config.js` and `apps/web/e2e/intake-profile-live-uat.spec.js` for real authenticated browser execution.
- Updated `apps/web/playwright.config.js` so credential-dependent live specifications remain isolated from fixture-backed browser regression.
- Updated this report with actual evidence and limitations. No production application behavior, authorization, approval, or deployment configuration was changed.

M17 decision: **PASS** for the approved Intake/Profile browser-to-FastAPI-to-PostgreSQL workflow. Full product production readiness remains **BLOCKED** by Market and Scheme source onboarding, controlled live Weather verification, persistent Escalation/Learning audit requirements, and the absence of a dedicated cross-system audit correlation field.

M17 recommendation status: completed by M18 for audit correlation and Escalation/Learning review auditing; external Market and Scheme source onboarding remains blocked pending approved datasets.

## 11. M18 Agent data sources and audit governance

### Baseline and verified changes

- Weather was already a bounded, read-only Open-Meteo client with coordinate validation, one-day forecasts, response-size limits, date validation, deterministic risk thresholds, sanitized 503 handling, and authenticated Admin/GIS Operator/ML Team routing.
- Market and Scheme already failed safely when their configured local source was absent. Their existing version-1 loaders remain compatible.
- Escalation and Learning were authenticated, deterministic, and advisory but previously stateless. Their permitted successful human-review operations now require an independently committed audit event before a result is returned.
- Generic execution remains disabled. Learning still performs no training, model update, feedback persistence, deployment, or external action.

### Weather provider verification

- One controlled live request used the existing client and Hyderabad coordinates (`17.385`, `78.4867`) on 2026-11-19.
- The provider returned source `Open-Meteo`, forecast date `2026-11-19`, all five requested measurements, `advisory_only=true`, and `persisted=false`.
- No forecast values were copied into fixtures or represented as durable operational metrics.
- Invalid coordinates remain rejected by the request model. Provider/network/format failures remain sanitized HTTP 503 responses.
- Readiness: **PASS for current read-only provider integration at the verification time**. Rate limits, long-term availability, and an operational SLA remain external dependencies.

### Market and Scheme data contracts

- No approved Market snapshot or authoritative Scheme catalogue was found or configured. No price, scheme, eligibility rule, or operational readiness claim was fabricated.
- Market schema version 2 now requires snapshot ID, publication timestamp, source name, HTTPS source URL, record-level market ID, observation timestamp, commodity/market identity, price date, price range, and calculated freshness. Version 1 remains readable for compatibility.
- Scheme schema version 2 now requires catalogue ID, publication timestamp, authority name, official HTTPS authority URL, record effective dates, source verification date, eligibility rules, supporting documents, and explanations. Expired or not-yet-effective schemes cannot be classified as potential matches. Version 1 remains readable for compatibility.
- Readiness: **MARKET BLOCKED** and **SCHEME BLOCKED** until separately approved authoritative files are supplied and operational ownership, refresh cadence, and expiry policies are established.

### Persistent review audit and correlation

- New migration: `0012_agent_audit_governance`, chained from `0011_persistent_auth_sessions`; no previously applied migration was modified.
- The migration makes the legacy parcel reference nullable for non-parcel reviews, adds nullable `subject_id`, adds indexed nullable `correlation_id`, and preserves legacy rows without backfilling or rewriting protected history.
- New Intake/Profile results carry the same generated UUID correlation as their audit event.
- Escalation and Learning review results carry the same generated UUID correlation as their independently committed audit record.
- Review audit records persist only actor, role, subject reference, operation, outcome, reason, correlation, and timestamp. Evidence descriptions, feedback text, notes, tokens, and credentials are not written to this audit table.
- Audit storage failures return HTTP 503 and prevent successful review responses.
- The existing update/delete and truncate triggers remain installed and effective.

### Disposable PostgreSQL evidence

- A workspace-owned PostgreSQL 17 cluster was created on `127.0.0.1:55432` with the exact guarded database name `agrinexa_agent_audit_test`; port 5432 was not accessed.
- The database was migrated through 0011, a legacy eight-column audit row was inserted, and migration 0012 was applied separately.
- Alembic head became `0012_agent_audit_governance`; the legacy row retained its original ID and parcel ID, with new fields null; both append-only triggers remained present.
- Real service executions committed `ESCALATION_REVIEW` for `M18-CASE` and `LEARNING_REVIEW` for `M18-REVIEW`, each with a non-null correlation, `allowed` outcome, and `AUTHORIZED` reason.
- The Learning result simultaneously verified `training_performed=false`, `model_updated=false`, and `feedback_persisted=false`.

### M18 verification results

| Suite | Passed | Failed | Skipped/blocked | Result |
|---|---:|---:|---:|---|
| Complete backend suite excluding separately run live audit files | 1,055 | 0 | 5 | PASS |
| Live PostgreSQL migration/append-only suite | 10 | 0 | 0 | PASS |
| Frontend Node tests | 41 | 0 | 0 | PASS |
| Playwright Chromium regression | 9 | 0 | 0 | PASS |
| Frontend production build | n/a | 0 | 0 | PASS; 1,657 modules transformed |
| Controlled live Weather request | 1 | 0 | 0 | PASS at verification time |
| Approved Market dataset | 0 | 0 | 1 blocked | Not supplied |
| Authoritative Scheme catalogue | 0 | 0 | 1 blocked | Not supplied |

### Agent-by-agent readiness after M18

| Agent | Readiness | Evidence / remaining limitation |
|---|---|---|
| INTAKE | PASS for approved preview | M17 browser/database flow preserved; correlated append-only audit now supported. |
| PROFILE | PASS for approved preview | Deterministic read-only profile and correlated audit; generated profile remains intentionally non-persistent. |
| WEATHER | PASS for read-only integration | Live provider verified once; external availability and SLA remain provider-dependent. |
| CROP_ADVISORY | PASS for conservative advisory scope | Existing deterministic and safety-restricted behavior unchanged. |
| MARKET | BLOCKED | Version-2 approved snapshot contract implemented; no approved snapshot supplied. |
| SCHEME | BLOCKED | Version-2 authoritative catalogue contract implemented; no catalogue supplied. |
| ESCALATION | PASS for human-review screening | Successful permitted reviews are append-only audited and fail closed; no dispatch or external action. |
| LEARNING | PASS for manual review scope | Successful permitted reviews are append-only audited and fail closed; no automatic learning, training, persistence, or model update. |

### M18 modified files

- Backend audit: `agent_audit.py`, `agent_audit_models.py`, `agent_audit_sink.py`, `agent_audited_pipeline.py`, `agent_pipeline.py`, and new `agent_review_audit_service.py`.
- Backend workflows: `escalation_agent.py`, `escalation_agent_router.py`, `learning_agent.py`, `learning_agent_router.py`, `market_agent.py`, and `scheme_agent.py`.
- Migration: new `migrations/versions/0012_agent_audit_governance.py`.
- Frontend: `AgentEscalationWorkspace.jsx`, `AgentLearningWorkspace.jsx`, `AgentMarketWorkspace.jsx`, and `AgentSchemeWorkspace.jsx`.
- Tests: updated audit schema/live migration, functional HTTP, Escalation/Learning router, Market, and Scheme tests; added review-audit service and 0012 migration tests.
- Documentation: this report.

M18 decision: **PASS** for Weather verification, audit correlation, migration compatibility, and persistent Escalation/Learning review auditing. Full production acceptance remains **BLOCKED** only for the Market and Scheme agents because approved authoritative datasets were not supplied.

Recommended next milestone: onboard separately approved Market and Scheme version-2 datasets in a controlled non-production environment, establish named refresh/expiry ownership, and run source-specific browser and freshness UAT without changing the disabled generic execution or learning controls.

## 12. M19 Market and Scheme data readiness

M19 assessed official Market and Telangana-relevant Scheme sources and added a controlled local version-2 lifecycle: immutable draft, validated, and approved copies; canonical content SHA-256; dataset version/import/license/original-unit provenance; record and duplicate validation; deterministic re-import behavior; explicit approval; and runtime rejection of any v2 file lacking approved governance or approved-directory placement. Existing v1 readers and router authorization remain compatible.

The frontend now distinguishes contract version from operator-assigned dataset version and displays publication/import/approval times, source identity, requested Market geography, freshness, and explicit missing-data states. Scheme screening remains advisory and incomplete/unverified rules remain human-review cases.

M19 verification: focused backend **49 passed, 0 failed**; frontend Node tests **41 passed, 0 failed**; frontend production build **PASS (1,657 modules transformed)**. Synthetic fixtures were confined to temporary test directories and are not approved application datasets. No external endpoint was activated and no production data was modified.

Detailed evidence and source findings: `docs/M19_MARKET_SCHEME_DATA_READINESS.md`.

M19 decision: **MARKET BLOCKED; SCHEME BLOCKED.** No separately approved authoritative snapshot/catalogue was supplied. Outstanding requirements are exact OGD resource/API approval and source-specific Market mapping/UAT; per-scheme current notification/guideline reconciliation; named data/policy approvers; refresh, expiry, attribution and stale-data ownership; immutable real extracts; and approved-dataset browser UAT.

## 13. M20 Authoritative data integration

M20 verified the official OGD/AGMARKNET resource identity (`9ef84268-d588-465a-a308-a864a43d0070`), API-key access model, GODL/NDSAP licensing context, daily granularity, and official state/district/market/commodity/variety/grade/arrival-date/min/max/modal field contract. A source-specific offline adapter now validates and maps an immutable captured JSON response into an unapproved v2 candidate while preserving source commodity, variety, grade, unit, retrieval time and date-only observation precision. It cannot approve or activate data. A project-owned API key was unavailable, so no third-party credential was used and no real observation was acquired.

Dataset decisions now require Admin role. Approval and rejection produce immutable artifacts with actor, role, timestamp and decision identifier; rejection also requires a substantive reason. Automated validation does not self-approve. Explicit absolute-path selection of immutable approved files preserves rollback to earlier approved versions.

Market API/UI now support market-name filtering and display variety/grade with existing source, version, unit, date, freshness and missing-data safeguards. Scheme sources were reassessed, but fragmented/undated rules were not converted into eligibility records; no scheme catalogue was acquired or approved.

M20 verification: focused suites **55 passed**; full backend repeat **1,069 passed, 15 skipped** after removing the known inherited incompatible `PROJ_LIB`; frontend Node **41 passed**; production build **PASS (1,657 modules)**. Playwright was **BLOCKED** because the configured local Chromium executable is absent; the bounded retry recorded one launch failure and did not run the remaining eight tests. Live credentialed acquisition, human approval, approved-data API comparison, and browser UAT remain blocked.

Detailed evidence: `docs/M20_AUTHORITATIVE_DATA_INTEGRATION_UAT.md`.

M20 decision: **MARKET BLOCKED; SCHEME BLOCKED.** Development is complete for work independent of credentials and human approval. Production readiness requires a project OGD key, immutable real capture, authorized Market approval, policy-owner Scheme evidence/approval, guarded live audit verification, and restored browser infrastructure.

## 14. M21 full eight-agent integration and production readiness

M21 restored the project-compatible Playwright Chromium revision 1254 in a workspace-local cache and updated all three Playwright configs to use that cache by default. Fixture-backed Chromium regression passed **9/9**. Real Vite → FastAPI browser tests passed **2/2** for Agent Metadata/role access and **1/1** for the parcel-backed Intake/Profile workflow with independently verified committed audit.

All 15 previously skipped backend tests were identified as guarded PostgreSQL/PostGIS tests. A workspace-owned PostgreSQL 17 cluster on `127.0.0.1:55432` hosted only `agrinexa_agent_audit_test` and marked `agrinexa_test`; all **15/15 passed**, including migration compatibility, audit persistence, append-only update/delete/truncate guards, PostGIS, concurrency and staged SCIM processing. The cluster and ephemeral data were removed afterward. The complete non-live suite passed **1,069** with the 15 guarded cases skipped by design; total applicable backend evidence across the required isolation modes is **1,084 passed, 0 failed, 0 unresolved skips**.

Live M21 evidence also includes one successful existing-client Open-Meteo request for Hyderabad and actual Escalation/Learning operations that committed correlated audit records while external action, training, model update and feedback persistence remained false. Frontend Node tests passed **41/41** and the production build passed with **1,657 modules transformed**.

Market still has no project OGD credential, real immutable capture, or human-approved snapshot. Scheme still has no policy-reviewed authoritative catalogue. A non-runtime evidence handoff was added at `docs/data/M21_SCHEME_HUMAN_REVIEW_CANDIDATES.json`; it preserves unknown dates/rules and cannot be consumed as a v2 catalogue.

Detailed evidence: `docs/M21_EIGHT_AGENT_PRODUCTION_READINESS.md`.

M21 agent classifications: Intake PASS, Profile PASS, Weather PASS at verification time, Crop Advisory PASS for conservative advisory scope, Market BLOCKED, Scheme BLOCKED, Escalation PASS for audited human review, Learning PASS for restricted audited manual review. Overall production acceptance remains **BLOCKED** until both authoritative datasets are explicitly approved and verified source-to-browser.

## 15. M22 production infrastructure and release readiness

M22 replaced the broken development-only container boundary with pinned, non-root backend and frontend images; unprivileged Nginx; internal-only API networking; a loopback production Compose template; Caddy HTTPS template; read-only filesystems and approved dataset mount; explicit secret/environment contracts; and fail-fast production configuration validation. No Redis or broker was introduced because the application does not use one.

New `/live` and `/ready` endpoints separate process health from PostgreSQL/migration/PostGIS/private-storage readiness. Sanitized JSON request logging and bounded `X-Request-ID` correlation were added without logging bodies, tokens, query strings or database parameters. Existing agent audit correlation remains unchanged.

An explicit migration gate now requires backup approval, expected starting revision, PostGIS and an advisory lock, then verifies head 0012 and both audit guards. Disposable evidence passed for migration 0011→0012 and custom-format dump restoration to a separate database; restored revision 0011 and PostGIS were verified. No automatic downgrade or application-start migration exists.

Regression: backend non-live **1,079 passed, 15 live separated**; guarded live PostgreSQL/PostGIS **15 passed**; applicable backend total **1,094 passed, 0 failed, 0 unresolved skips**; frontend **41 passed**; Chromium **9 passed**; build **PASS (1,657 modules)**; npm and Python audits reported **0 known vulnerabilities**; Compose rendering passed. Docker image builds and container staging are **BLOCKED** because the Docker engine is unavailable, although Docker CLI/Compose are installed.

A least-privilege non-deploying GitHub Actions workflow now validates backend, disposable PostGIS, frontend, advisories, images and Compose. Its remote execution is not claimed. DigitalOcean topology, costs, backups, monitoring, incident response, database/application rollback separation and manual deployment checklist are documented in `docs/M22_PRODUCTION_INFRASTRUCTURE_READINESS.md`.

M22 decision: local release engineering controls **PASS**; deployment remains unauthorized; full production readiness remains **BLOCKED** by unexecuted container staging, unresolved production evidence-storage architecture, operational approvals, and missing human-approved Market/Scheme datasets.
