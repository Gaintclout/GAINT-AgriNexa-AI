# M20 Authoritative Market and Scheme Data Integration UAT

Verification date: 2026-11-20 (Asia/Calcutta)

## Production-readiness decision

**MARKET: BLOCKED. SCHEME: BLOCKED.** M20 source discovery, source-specific Market mapping, approval authorization, rejection audit metadata, runtime filtering, and regression verification are complete. No project-owned OGD API credential was available, no authoritative response was acquired, no human reviewer approved a dataset, and no real dataset was activated. Scheme rules remain distributed across official pages without a reviewed canonical catalogue. Fixture-backed tests are not evidence of production data readiness.

## Existing implementation audit

M19 already supplied immutable draft, validated and approved directories; v2 schema validation; content SHA-256; import, publication and approval timestamps; source/license/original-unit provenance; duplicate and tamper detection; deterministic re-import; approved-directory runtime enforcement; v1 compatibility; authenticated dedicated routers; and provenance-aware Market/Scheme workspaces. M18 audit correlation, append-only workflow audit controls, disabled generic execution, and disabled automatic learning/training remain unchanged.

M20 did not duplicate those controls. It added only the missing source adapter, richer official fields, market-name filtering, Admin-only decisions, immutable rejection records, and associated tests/UI details.

## Market source inspection and access result

### Official source

- Publisher: Directorate of Marketing and Inspection, Department of Agriculture and Farmers Welfare, Ministry of Agriculture and Farmers Welfare.
- Catalogue: `https://www.data.gov.in/catalog/current-daily-price-various-commodities-various-markets-mandi`.
- Resource page: `https://www.data.gov.in/resource/current-daily-price-various-commodities-various-markets-mandi`.
- Resource ID: `9ef84268-d588-465a-a308-a864a43d0070`.
- API base: `https://api.data.gov.in/resource/9ef84268-d588-465a-a308-a864a43d0070`.
- Format/access: JSON REST resource using an `api-key` query parameter; OGD account/API-key management is the credential path. No project key was present. Third-party keys found in public examples were not used.
- Granularity: daily; the API record date is `arrival_date`, not a time-of-day observation.
- License: the catalogue is released under NDSAP and OGD content is governed by the resource license metadata/Government Open Data License - India. Attribution, non-endorsement, accuracy, and continuity conditions apply.
- Rate limits: an authoritative numeric rate limit was not exposed by the official pages inspected. It remains a credential/onboarding dependency and must not be guessed.

The official catalogue/resource pages intermittently returned HTTP 503 during inspection. The catalogue metadata remained discoverable, but no API request was attempted without a project-owned credential.

### Field mapping

| Official field | GAINT v2 field | Rule |
|---|---|---|
| `state` | `state` | Required trimmed text |
| `district` | `district` | Required trimmed text |
| `market` | `market`; deterministic `market_id` | ID is SHA-256-derived from state/district/market identity |
| `commodity` | `source_commodity`, normalized `commodity` | Only explicit supported mappings accepted; unknown names reject the import |
| `variety` | `variety` | Required, preserved verbatim after trimming |
| `grade` | `grade` | Required, preserved verbatim after trimming |
| `arrival_date` | `price_date`, `observed_at` | DD/MM/YYYY or ISO date; serialized at UTC midnight with `observation_time_precision=date`, so no time-of-day is claimed |
| `min_price` | `min_price_inr_per_quintal` | Numeric, bounded, and `min <= modal <= max` |
| `max_price` | `max_price_inr_per_quintal` | Same validation |
| `modal_price` | `modal_price_inr_per_quintal` | Same validation |
| resource unit | `original_price_unit` | `INR/quintal`; no conversion is performed |
| response `updated_date` | dataset `published_at` | Required official response metadata |
| local capture time | dataset `retrieved_at` | Timezone-aware, non-future timestamp supplied by controlled acquisition |

The offline adapter validates the resource identity/status, refuses empty responses, rejects unsupported commodities, malformed values, inconsistent prices, and duplicate market/commodity/variety/grade/date observations, then emits an **ungoverned v2 candidate only**. It cannot approve or activate data.

### Acquisition outcome

Real observations acquired: **none**. Dataset version/hash: **not applicable**. External dependency: a project-owned data.gov.in API key, confirmed rate limits, an immutable raw JSON capture, and human approval. The documented adapter allows an authorized operator to capture the response separately and import it without embedding a credential in code or provenance files.

## Government scheme source inspection

Authoritative sources assessed remained:

- PM-KISAN official portal and revised operational guidelines: `https://pmkisan.gov.in/`.
- Telangana Horticulture Department TGMIP FAQ: `https://horticulturedept.telangana.gov.in/horticulturetelangana/MIP_FAQ.aspx`.
- Telangana MeeSeva agriculture services: `https://ts.meeseva.telangana.gov.in/TSDeptPortal/UserInterface/Services.html`.
- Telangana official district agriculture-scheme inventories, including `https://mulugu.telangana.gov.in/agriculture-schemes/`.

PM-KISAN provides central authority, operational date, benefit structure, family definition, exclusions, eKYC and registration/status paths. TGMIP supplies Telangana scope, documents/application channel, once-in-seven-years language and an area limit, but the FAQ does not provide sufficient revision/effective-date control for automated authoritative screening. MeeSeva describes application services, charges, SLAs and approving officers but not complete current eligibility. District inventories identify programmes but are not statewide revision-controlled rulebooks.

No scheme record was created from narrative fragments. Required human work remains: reconcile current notifications/guidelines with portals; verify effective dates, benefits, limits, documents, application processes and geography; record conflicting or unknown conditions; and have the responsible policy reviewer approve the catalogue. Until then, uncertain conditions must remain `needs_review`/human verification and no benefit entitlement may be claimed.

## Dataset decisions and rollback

- `approve_validated` now requires `reviewer_role=admin`; any other role is rejected before a file is written.
- Approval records actor, role, timestamp and a deterministic decision identifier inside the immutable approved artifact.
- `reject_validated` requires Admin role and a substantive reason, then writes a separate immutable rejected artifact containing actor, role, timestamp, reason and decision identifier.
- Approved snapshots are never overwritten. Runtime selection continues to use an explicit absolute configured path, so rollback means selecting a previously approved immutable version; draft, validated and rejected files cannot load.
- Automated validation never self-approves. No M20 real-data approval action occurred.

## Agent and frontend integration

Market requests now support exact market-name filtering in addition to commodity/state/district. Responses preserve source commodity, variety, grade, original unit and date-only observation precision. Existing freshness classification, stale labels, source identity, dataset version, missing-data behavior, and non-guaranteed wholesale-price disclaimer remain.

The Market workspace adds a market filter and shows variety/grade with each observation. Scheme behavior remains conservative: effective-date and geographic mismatches are explained, missing attributes produce review outcomes, unverified rules require human review, and the UI never states government approval or entitlement. Both workspaces retain authenticated requests, loading/error/empty states, responsive existing design classes, and explicit source/provenance displays.

## UAT and regression evidence

| Suite | Passed | Failed | Skipped/blocked | Result |
|---|---:|---:|---:|---|
| M20 focused Market/Scheme/source/decision tests | 55 | 0 | 0 | PASS |
| Complete backend regression after removing inherited incompatible `PROJ_LIB` | 1,069 | 0 | 15 | PASS |
| Initial backend run with machine `PROJ_LIB` | 1,045 | 24 | 15 | ENVIRONMENT FAILURE; all 24 were unrelated Rasterio/PROJ failures |
| Frontend Node tests | 41 | 0 | 0 | PASS |
| Frontend production build | n/a | 0 | 0 | PASS; 1,657 modules transformed |
| Playwright Chromium | 0 | 1 launch failure | 8 not run in bounded retry | BLOCKED: configured Chromium executable absent |
| Real OGD acquisition/import | 0 | 0 | 1 blocked | Project API key unavailable |
| Human dataset approval | 0 | 0 | 1 blocked | No explicit authorized review |
| Approved-data browser UAT | 0 | 0 | 1 blocked | No approved data and browser unavailable |

The 15 backend skips are environment-dependent/live suites, including PostgreSQL/browser or external integration conditions. No production database was accessed. The first browser invocation showed nine failed markers and hung during web-server cleanup; a bounded retry stopped after the first failure and established the cause: the configured `chromium_headless_shell-1254` executable does not exist under the local Playwright cache. No browser was downloaded and user-level tooling was not changed.

Security regression confirms dedicated routes remain role-protected; generic agent execution, automatic learning, training, model update and unauthorized external actions remain disabled. No password, production row, deployment, or source configuration changed.

## Remaining dependencies and acceptance

1. Obtain a project-owned OGD API key; confirm official rate limits; capture and checksum a bounded official response under the applicable license.
2. Import and validate the real Market candidate, review mapping/coverage/freshness, then obtain an explicit Admin reviewer decision. Record the resulting dataset version and SHA-256.
3. Assemble a canonical current scheme evidence pack and obtain named policy-owner verification and Admin approval.
4. Exercise both APIs against approved versions and compare every returned record to the immutable source capture.
5. Install/restore the project-pinned Playwright Chromium and run Market/Scheme browser scenarios.
6. Run the live PostgreSQL audit/migration suite in the guarded disposable database if required for release evidence.

M20 development is complete for all work not requiring credentials, human approval, or missing browser infrastructure. Product acceptance remains **BLOCKED** for Market and Scheme.
