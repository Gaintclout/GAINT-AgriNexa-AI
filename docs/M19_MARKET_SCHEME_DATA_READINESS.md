# M19 Market and Scheme Data Readiness

Verification date: 2026-11-20 (Asia/Calcutta)

## Decision

**MARKET: BLOCKED. SCHEME: BLOCKED.** The versioned ingestion, validation, approval gate, provenance display, and technical UAT are implemented. No separately approved authoritative Market snapshot or Scheme catalogue is present or configured. Synthetic records were used only in isolated tests and are not application data.

## Scope and existing controls

The dedicated authenticated routes remain `POST /api/v1/agents/market/prices` and `POST /api/v1/agents/schemes/screen`. Admin, GIS Operator, and ML Team roles are allowed; the routers re-check that the database account exists, is active, and has the token role. Provider errors are sanitized. Generic agent execution remains disabled. Version-1 local files remain readable for backward compatibility; only governed version-2 files can enter the new approval workflow.

## Official market sources assessed

### AGMARKNET and OGD Platform India

- **Organizations:** Directorate of Marketing and Inspection (DMI), Department of Agriculture and Farmers Welfare, Ministry of Agriculture and Farmers Welfare; AGMARKNET is the originating system. The National Informatics Centre hosts the OGD Platform.
- **Official access:** the OGD catalogue is `https://data.gov.in/catalog/current-daily-price-various-commodities-various-markets-mandi`, with resource pages for current daily prices and variety-wise prices. The catalogue advertises CSV/download, preview, and Data API functions. The AGMARKNET public site and its reports were assessed as human-facing sources; their existence is not treated as approval for an undocumented machine interface.
- **Coverage and fields:** the catalogue describes daily wholesale minimum, maximum, and modal prices across Indian states, districts, markets, commodities, and varieties. The resource page explicitly lists State, District, Market, Commodity, and Variety; price/date fields must be confirmed from the exact selected resource response before mapping.
- **Units:** AGMARKNET documentation says entries are shown in the standard unit reflected on the portal. GAINT's current v2 contract accepts only `INR/quintal`; an onboarding owner must verify the exact resource unit and reject or explicitly transform any other unit while preserving the original unit.
- **Timestamps and refresh:** catalogue granularity is Daily. Resource/catalogue `Updated On` is publication metadata, not a record observation timestamp. Onboarding must preserve both the record arrival/price date and the retrieval/import time; it must not invent an observation time when the resource does not provide one.
- **License/reuse:** the catalogue is released under NDSAP and the OGD terms point to the dataset license metadata. The Government Open Data License - India permits lawful commercial and non-commercial reuse and derivatives subject to attribution, non-endorsement, and other terms. The exact resource license metadata and attribution statement must be archived with each approved import.
- **Authentication:** Data API controls were visible, but this assessment did not activate or call an API and did not establish whether the selected endpoint requires a registered API key. Authentication and rate limits therefore remain an onboarding check.
- **Quality limitations:** reporting can be delayed or missing; min/modal/max consistency and anomalous-data correction do not prove completeness; commodity/variety names and market identity require normalization; catalogue update timestamps do not establish freshness of every record; continued supply is not guaranteed under the OGD license.

No market source was activated. Required approval evidence is: exact resource identifier and endpoint/download procedure, captured schema, confirmed unit, API-key/rate-limit terms, license/attribution record, refresh owner and cadence, immutable raw extract checksum, and source-specific mapping test.

## Official scheme sources assessed

The intended deployment geography is treated as **Telangana**, based on the project's geography fixtures and prior Hyderabad UAT. This is an architectural assumption for assessment only, not activation.

| Scheme/source | Authority and official source | Findings | Approval status |
|---|---|---|---|
| PM-KISAN | Department of Agriculture and Farmers Welfare, Government of India; `https://pmkisan.gov.in/` and its revised operational-guidelines PDF | Central scheme; portal states it has operated since 2018-12-01, identifies landholding farmer families, mandatory eKYC, exclusions, direct bank transfer, registration/status flows. The current portal and operational guidelines must be reconciled because historical FAQs/guidelines can differ. | Human verification required; no catalogue record created. |
| Telangana State Micro Irrigation Project (TGMIP) | Telangana Horticulture Department; `https://horticulturedept.telangana.gov.in/horticulturetelangana/MIP_FAQ.aspx` | FAQ states Telangana-wide scope, application at MeeSeva, land document/Aadhaar/caste certificate, once-in-seven-years rule, and benefit area up to 5 ha subject to guidelines/water scarcity. It does not expose a revision/effective date adequate for automated eligibility. | Human verification required; no catalogue record created. |
| Telangana MeeSeva agriculture services | Government of Telangana; `https://ts.meeseva.telangana.gov.in/TSDeptPortal/UserInterface/Services.html` | Lists crop insurance, subsidized seed distribution and farm mechanization services, service charges, SLAs, and MAO approval. The page does not provide a complete current eligibility/document/effective-date rule set for each service. | Discovery/application-process source only; not sufficient for eligibility records. |
| Telangana agriculture scheme listings | Government of Telangana district portals, including `https://mulugu.telangana.gov.in/agriculture-schemes/` | Useful inventory of state and centrally sponsored schemes, but an inventory is not a complete authoritative eligibility contract. District pages may not establish statewide revision control. | Discovery only; human verification required. |

Scheme approval requires, per scheme: issuing authority, canonical official URL, exact current eligibility and exclusions, effective-from/effective-until or an explicitly approved open-ended status, required documents, application channel, state/district applicability, source revision/verification date, named verifier, and recorded ambiguity. Incomplete rules must retain `eligibility_rules_verified=false`; the UI can only show `needs_review`, never confirmed eligibility.

## Version-2 contracts and ingestion

Market v2 requires snapshot identity/publication/source metadata and validated records with market identity, geography, commodity, price date, observation timestamp, min/modal/max prices, and source provenance. Scheme v2 requires catalogue/authority metadata and records with scheme identity, government level, geographic lists, screening attributes, documents, application guidance, official URL, verification date, effective dates, and a verification flag.

`agent_dataset_ingestion.py` provides a local, controlled workflow:

1. `import_draft` reads an absolute JSON file under a 2 MB limit, records the dataset kind/version, import timestamp, license, original units and canonical SHA-256, then creates an immutable draft.
2. `validate_draft` enforces schema v2, required dataset fields, HTTPS provenance, non-future publication time, record validation, supported commodities/units, list/range/date constraints, and duplicate identifiers before creating an immutable validated copy.
3. `approve_validated` revalidates content and creates a separate approved copy with approver and approval timestamp. Future timestamps and approval before import are rejected.
4. Existing files are never silently overwritten. An identical operation is idempotent; conflicting content at the same governed path is rejected.
5. Runtime v2 loaders require valid approved governance metadata, matching SHA-256, and placement in the `approved` directory. Draft or validated data cannot answer agent requests.

The canonical digest excludes governance metadata so source content has a stable identity across lifecycle states. Original price units are preserved in governance and Market v2 currently rejects anything other than `INR/quintal`. Dataset version, import time, approval time, publication time, source identity, freshness, and requested geography are exposed to the frontend. Contract version and dataset version are deliberately distinct.

## Controlled UAT evidence

Synthetic fixtures are conspicuously named and use `example.gov.in`; they exist only in pytest temporary directories.

| Verification | Result |
|---|---|
| Draft -> validated -> approved deterministic flow for both kinds | PASS |
| Invalid JSON/schema/record and unsupported Market unit | PASS |
| Duplicate identifiers and duplicate list values | PASS |
| Tamper/digest mismatch and silent overwrite protection | PASS |
| Future/import/approval ordering | PASS |
| Draft/validated runtime rejection; approved v2 loading | PASS |
| v1 backward compatibility and v2 provenance metadata | PASS |
| Market/Scheme router account and authorization checks | PASS |
| Geographic filtering/screening, stale price classification, ineffective Scheme handling, and missing-source behavior | PASS |
| Focused backend suites | **49 passed, 0 failed** |
| Frontend Node contract/regression tests | **41 passed, 0 failed** |
| Frontend production build | **PASS; 1,657 modules transformed** |

No production database, production data, credentials, deployment setting, live source, or external scheme application was changed.

## Remaining blockers and approval requirements

1. A data owner must select and approve an exact OGD Market resource, access mechanism, mapping, unit, license attribution, credential/rate-limit treatment, refresh cadence, stale threshold, and expiry/escalation owner.
2. An immutable real extract must be imported, reviewed for Telangana commodity/market coverage and observation semantics, and approved by an identified authorized approver.
3. A scheme policy owner must approve a canonical source bundle per scheme, reconcile current portals with guidelines/notifications, and record effective dates, documents, application steps, geography, and ambiguities.
4. Source-specific parser tests, controlled connectivity/download evidence, and browser UAT with approved non-production datasets remain outstanding.
5. Operational storage permissions must prevent application/service identities from writing to approved directories; the code gate supplements but does not replace filesystem controls.

Production readiness remains **BLOCKED** for both agents. The technical workflow is ready to receive candidate data, but no result may be described as authoritative until all approval evidence above exists.
