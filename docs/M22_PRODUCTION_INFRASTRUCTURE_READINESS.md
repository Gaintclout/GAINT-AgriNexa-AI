# M22 Production Infrastructure, Security Hardening and Release Readiness

Verification date: 2026-11-20 (Asia/Calcutta)

## Decision

**Release engineering: PASS for locally implemented controls. Deployment authorization: NOT GRANTED. Overall production readiness: BLOCKED.** Container definitions, environment validation, health/readiness, migration gating, CI, backup/restore procedures and operational guidance are prepared. Actual image builds/staging are blocked because the Docker engine is not running. Market and Scheme remain blocked by missing approved authoritative datasets. No cloud or production resource was created, accessed or changed.

## Existing architecture assessment

### Runtime components

- **Frontend:** React 18/Vite single-page application. It uses authenticated same-origin API requests and has no server-side Node runtime requirement after build.
- **API:** FastAPI/Uvicorn with dedicated routers for identity, registry/GIS, SCIM, field verification and eight governed agents.
- **Database:** PostgreSQL with PostGIS, Alembic migrations through `0012_agent_audit_governance`, persistent refresh sessions, parcel geometry, SCIM state, and append-only agent audit records.
- **Evidence storage:** private content-addressed filesystem storage for JPEG/PNG/WebP evidence with decode verification, SHA-256 identity, exclusive creation and 8 MB limit.
- **Datasets:** local immutable Market/Scheme artifacts with draft/validated/approved separation. Runtime paths are explicit; production mounts approved datasets read-only.
- **External read-only dependencies:** Open-Meteo; data.gov.in acquisition requires a project-owned key outside runtime.
- **No Redis/message queue:** no code dependency exists. SCIM leasing/jobs use PostgreSQL. M22 does not add Redis or a broker.

Before M22, the backend Dockerfile referenced nonexistent `requirements-sprint1.txt`, production dependencies were incomplete, no frontend/reverse-proxy image existed, Compose exposed only a development API, liveness/readiness were conflated, and no CI workflow existed.

## Recommended DigitalOcean topology

### Recommended initial topology

1. Bangalore-region Ubuntu Droplet, initially 2 vCPU/4 GiB RAM, running rootless/restricted Docker Compose.
2. Host Caddy terminates HTTPS on ports 80/443 and proxies only to `127.0.0.1:8080`. The frontend Nginx container is the sole published application port; API port 8000 is internal only.
3. DigitalOcean Managed PostgreSQL on private networking with TLS required and firewall restricted to the application Droplet and release runner. DigitalOcean currently lists `postgis` as a supported PostgreSQL extension, but the exact selected engine version/edition must be checked immediately before provisioning: `https://docs.digitalocean.com/products/databases/postgresql/details/supported-extensions/`.
4. Encrypted Block Storage volume for private evidence photos and a separate read-only host directory for approved dataset artifacts. Current code uses filesystem semantics; switching directly to Spaces would require a tested S3 storage adapter and is not assumed.
5. Spaces may hold encrypted logical database exports and replicated evidence backups. Spaces is S3-compatible but does **not** include built-in backups, so replication must be scheduled and monitored: `https://docs.digitalocean.com/products/spaces/details/limits/`.
6. VPC/private networking for application-to-database traffic. Cloud firewall permits public 80/443 only, SSH only from an administrative allowlist/VPN, and no public PostgreSQL/API ports.
7. DigitalOcean monitoring/uptime alerts plus external error tracking/log retention. DNS A/AAAA records point to the Droplet or a later load balancer; CAA records restrict certificate authorities.

### Droplet versus App Platform

App Platform reduces host maintenance and supports readiness/liveness checks, but its container filesystem is ephemeral and it does not support volumes (`https://docs.digitalocean.com/products/app-platform/details/limits/`). The existing private evidence store therefore cannot safely run there without a Spaces adapter. A Droplet plus attached encrypted storage matches current code and provides controlled reverse-proxy/network configuration, at the cost of OS patching, capacity management and a single-host failure domain.

For higher availability, first implement/test Spaces-backed evidence storage, then use two application instances behind a load balancer or App Platform with Managed PostgreSQL HA. Do not scale the current filesystem-backed service horizontally because evidence would diverge.

### Indicative sizing and cost assumptions

As of the verification date, official pricing lists a Basic 2 vCPU/4 GiB Droplet at about USD 24/month, managed PostgreSQL starting at USD 15/month for a non-HA single node, HA beginning with a primary plus matching standby (about USD 60/month at the cited entry tier), Spaces from USD 5/month, and block storage from USD 10/month. Droplet backup pricing is percentage-based. Sources: `https://www.digitalocean.com/pricing/droplets`, `https://docs.digitalocean.com/products/databases/postgresql/details/pricing/`, and `https://www.digitalocean.com/pricing`.

Budgetary starting points, excluding tax, bandwidth overages, DNS, monitoring and support:

- Non-HA pilot: roughly USD 54+/month (USD 24 Droplet + USD 15 DB + USD 10 volume + USD 5 Spaces), plus backups.
- Production baseline with managed DB standby: roughly USD 99+/month using the same compute/storage assumptions, plus backups and any load balancer.

These are planning assumptions, not quotes. Re-price and load-test before approval.

## Container and deployment configuration

- `services/api/Dockerfile`: pinned Python 3.13.9 base; exact production dependencies; non-root UID/GID 10001; migrations included but never auto-run; process liveness check; SIGTERM and 30-second graceful shutdown; no Uvicorn access log because sanitized request middleware owns request logging.
- `apps/web/Dockerfile`: pinned Node 22.21.1 build stage and unprivileged Nginx runtime; no source/dev dependencies in runtime.
- `apps/web/nginx.production.conf`: SPA serving, internal API proxy, upload limit, timeouts, CSP, frame denial, MIME sniffing prevention, restrictive permissions policy and immutable asset caching.
- `deploy/compose.production.yml`: immutable image tag required, API unexposed, frontend bound only to loopback, read-only root filesystems, dropped capabilities, `no-new-privileges`, tmpfs, restart policies, readiness-gated dependency, private photo volume and read-only approved dataset bind.
- `deploy/Caddyfile.example`: HTTPS termination/HSTS template. Replace the example domain before use.
- `.dockerignore` files prevent secrets, tests, caches, browser binaries, archives and built artifacts from entering contexts.

Compose rendered successfully with the sanitized example. Docker image build and running-stack smoke tests are **BLOCKED**: Docker CLI/Compose are installed, but `//./pipe/docker_engine` is absent and the Docker daemon is not running. Reproducible commands:

```text
docker build -t agrinexa-api:<immutable-tag> services/api
docker build -t agrinexa-web:<immutable-tag> apps/web
docker compose --env-file .env.production -f deploy/compose.production.yml config
docker compose --env-file .env.production -f deploy/compose.production.yml up -d
docker compose --env-file .env.production -f deploy/compose.production.yml ps
curl --fail http://127.0.0.1:8080/live
curl --fail http://127.0.0.1:8080/ready
docker compose --env-file .env.production -f deploy/compose.production.yml down
```

## Environment and secrets security

Sanitized contracts are `.env.production.example` and the acquisition-only `.env.import.example`. Real `.env`, production env, backup approvals, caches and build outputs are ignored.

| Variable | Purpose / production rule |
|---|---|
| `AGRINEXA_ENV` | Must equal `production` to enable fail-fast validation. |
| `DATABASE_URL` | Least-privilege application role; private host; PostgreSQL; `sslmode=require` or stronger. Never use owner/migration credentials at runtime. |
| `AGRINEXA_JWT_SECRET` | Secret manager value, minimum 48 characters under production validation; rotate through an approved session-revocation plan. |
| `AGRINEXA_CORS_ORIGINS` | Explicit HTTPS origin(s); wildcard, localhost and HTTP rejected in production. |
| `AGRINEXA_PRIVATE_PHOTO_DIR` | Absolute writable private volume path. |
| `AGRINEXA_MARKET_SNAPSHOT_PATH` | Blank until approved; if set, must be under `/var/lib/agrinexa/datasets/approved`. |
| `AGRINEXA_SCHEME_CATALOGUE_PATH` | Same approved-storage rule. |
| `AGRINEXA_APPROVED_DATASET_DIR` | Host bind mounted read-only into runtime. |
| `DATA_GOV_IN_API_KEY` | Controlled import process only; deliberately absent from runtime env/Compose. |

Refresh cookies already use the `__Host-` prefix, Secure, HttpOnly, SameSite=Strict and `/` path. Refresh tokens are stored only as SHA-256 digests, rotated atomically, and revoked on logout. Access tokens expire after 15 minutes; refresh sessions after seven days. Origin checks use forwarded HTTPS information. Database engine parameters are hidden and exception responses/logs omit credentials.

Recommended DigitalOcean secret handling: inject secrets from an access-controlled root-readable host environment file or deployment secret store; restrict file mode to 0600; never pass acquisition keys into the API; rotate credentials with dual-role/connection-drain procedures; and use separate application, migration, backup and monitoring database roles.

## Liveness, readiness and observability

- `/live`: process-only liveness; no database or secret details.
- `/ready`: HTTP 200 only when PostgreSQL connects, Alembic head is exactly 0012, PostGIS exists, and private photo storage is present; otherwise sanitized HTTP 503 with boolean checks.
- `/health`: retained for backward compatibility and treated as liveness, not readiness.
- Request middleware accepts only bounded safe request IDs or generates a UUID, returns `X-Request-ID`, and emits JSON with UTC timestamp, level, logger, method, path, status and duration. It does not log bodies, tokens, query strings or database parameters.
- Application-level agent correlation IDs remain independent and persist in append-only audit rows.

Operational alerts:

- `/live` failure: page immediately; restart service after bounded retries.
- `/ready` failure: remove traffic; alert after two consecutive failures; investigate DB/migration/storage flags.
- CPU >80% for 10 minutes, memory >85%, disk/volume >80%, inode pressure, container restart loops, TLS expiry <21 days, database connection/storage thresholds and replication/failover events.
- Daily check that both audit triggers exist; alert on any rejected mutation attempt or missing trigger.
- Backup job missed/failed, restore-test overdue, dataset freshness threshold exceeded, and Open-Meteo/provider failure-rate alerts.
- Send structured logs to a restricted central sink; define retention/redaction and incident access. Configure an error-monitoring DSN only through secrets.

## Controlled migration and recovery procedure

`tools/release_migrate.py` is an explicit operator command and is never called by application startup. It:

1. Parses a PostgreSQL URL without printing credentials.
2. Requires `AGRINEXA_EXPECTED_CURRENT_REVISION` to match the live database.
3. Requires an absolute JSON backup-approval artifact containing database, backup reference, approver and timestamp.
4. Verifies database identity, current revision and PostGIS.
5. Takes a PostgreSQL advisory lock.
6. Runs `alembic upgrade head` explicitly.
7. Verifies head 0012 and both append-only audit triggers.
8. Stops non-zero on any mismatch/failure. It performs no automatic downgrade.

The disposable test upgraded 0011→0012 successfully and verified both triggers. Migration 0012 contains repeated `downgrade` definitions inherited from M18; Python uses the final fail-closed definition and upgrade is unaffected. The applied migration was intentionally not rewritten. Clean this source duplication only through an approved migration-history governance decision, never by silently changing an applied release artifact.

Application rollback means redeploying the prior immutable application images while leaving the forward-compatible database at its migrated revision. Database recovery is separate: stop writers, restore the approved pre-migration backup to a new cluster/database, verify PostGIS/schema/audit guards/data counts, redirect only after approval, and retain the failed database for investigation. Never run automatic destructive Alembic downgrade.

## Backup and disaster recovery

Proposed targets after business approval:

- Database: managed continuous recovery where available plus daily encrypted logical/custom-format export; 30 daily, 12 monthly and 7-year annual retention only if policy/legal owners approve.
- Evidence photos: encrypted volume snapshots plus daily incremental copy to a private backup Space or independent region/account. Spaces has no built-in backup; test object enumeration, hashes and restore permissions.
- Approved datasets/configuration: immutable versioned copies, SHA-256 manifests and provenance in a restricted backup location. Secrets are backed up only in the secret manager, not application archives.
- RPO target: 15 minutes for database when PITR is enabled; 24 hours for photos/datasets until continuous replication exists.
- RTO target: 4 hours for database/application and 8 hours for bulk evidence recovery. Validate with measured quarterly exercises.

M22 evidence: a PostgreSQL custom-format dump at revision 0011 with PostGIS was created, the source was migrated to 0012, the dump was restored into a separate database, and restored revision 0011 plus PostGIS were verified. All disposable databases, dump files and approval artifacts were removed afterward. Photo/object restore is **NOT TESTED** because no object-storage adapter or disposable Spaces credential exists.

Responsibilities: Release Manager approves backup/migration; DBA executes and verifies DB recovery; Security reviews secret/audit integrity; Application Owner verifies health and smoke tests; Data Governance approves Market/Scheme artifacts; Incident Commander authorizes traffic cutover.

## CI/CD

`.github/workflows/release-validation.yml` has read-only repository permission and no deployment job. It runs:

- Python compile, non-live backend tests and `pip-audit`.
- Guarded PostGIS service setup and the 15 live PostgreSQL/PostGIS tests in their required isolated phase.
- Frontend clean install, tests, production build and `npm audit`.
- Backend/frontend Docker builds and production Compose rendering.

Any future deployment workflow must be separate, target a protected GitHub Environment, require named manual reviewers, use short-lived credentials, verify immutable image digests and never auto-run database migration from application startup.

Local advisory results: Python pinned production requirements **0 known vulnerabilities**; npm **0 vulnerabilities**. Workflow execution itself is **NOT TESTED** because this workspace is not a Git repository and no remote CI run was authorized.

## Staging and regression evidence

| Verification | Passed | Failed | Skipped/blocked | Result |
|---|---:|---:|---:|---|
| Backend non-live suite | 1,079 | 0 | 15 live separated | PASS |
| Guarded PostgreSQL/PostGIS live suite | 15 | 0 | 0 | PASS |
| Applicable backend total | **1,094** | **0** | **0 unresolved** | PASS |
| Focused production config/health/security | 29 | 0 | 0 | PASS; included in backend total |
| Frontend Node | 41 | 0 | 0 | PASS |
| Playwright Chromium | 9 | 0 | 0 | PASS; fixture-backed |
| Frontend build | n/a | 0 | 0 | PASS; 1,657 modules |
| Python dependency audit | 0 vulnerabilities | n/a | 0 | PASS |
| npm dependency audit | 0 vulnerabilities | n/a | 0 | PASS |
| Compose render | 1 | 0 | 0 | PASS |
| Migration gate | 1 | 0 | 0 | PASS on disposable database |
| Database dump/restore | 1 | 0 | 0 | PASS on disposable database |
| Docker image builds | 0 | 0 | 2 blocked | Docker engine unavailable |
| Container staging smoke/restart | 0 | 0 | 1 blocked | Docker engine unavailable |
| Spaces photo backup/restore | 0 | 0 | 1 not tested | No adapter/credential |

The first backend run after replacing the broken Dockerfile had one obsolete contract-test failure expecting the nonexistent requirements filename. The test was strengthened to assert the actual pinned dependencies and non-root image, then the complete repeat passed. Pytest cache writes remain denied under `services/api/.pytest_cache`; isolated basetemp paths work.

## Eight-agent production governance

| Agent | Production configuration |
|---|---|
| Intake/Profile | Only approved read-only preview; authorization, parcel ownership, correlation and fail-closed audit retained. |
| Weather | Bounded read-only Open-Meteo client; advisory only; provider failures sanitized. |
| Crop Advisory | Conservative deterministic advisory; unsupported evidence not invented. |
| Market | **BLOCKED** until human-approved artifact; runtime path blank by default and restricted to approved read-only mount. |
| Scheme | **BLOCKED** until policy-reviewed human-approved catalogue; same mount/path restrictions. |
| Escalation | Audited screening only; external action remains false/disabled. |
| Learning | Restricted audited manual review; training, model update and feedback persistence remain false. |

Generic execution remains disabled for all agents. No automatic learning, model training, dataset self-approval or external escalation action was enabled.

## Remaining blockers

1. Build images and run production-equivalent Compose startup/restart/recovery when an approved Docker engine is available.
2. Provisioning design review: exact DigitalOcean PostgreSQL version/tier/PostGIS confirmation, VPC/firewall, DNS/domain, TLS, secret store and cost approval.
3. Select and implement the production evidence-storage strategy. Current Droplet volume is single-host; App Platform/horizontal scaling requires a tested Spaces adapter.
4. Complete real Spaces/evidence backup and restore exercise.
5. Obtain and approve authoritative Market and Scheme datasets; run source-to-browser UAT.
6. Run the new CI workflow in an actual repository and pin third-party Actions by commit SHA if organizational policy requires it.
7. Define operational owners, on-call escalation, log retention, RPO/RTO approval and incident exercises.

## Manual deployment checklist

1. Obtain Change, Security, Data Governance and Release Manager approvals; confirm this document does not itself authorize deployment.
2. Re-run pricing and verify selected managed PostgreSQL tier supports PostGIS.
3. Provision VPC, firewall, managed DB, encrypted storage, Droplet, DNS and monitoring through reviewed infrastructure-as-code.
4. Create least-privilege DB roles; enable PostGIS; test TLS; deny public DB access.
5. Store real secrets outside Git; set 0600 permissions; confirm acquisition key is absent from runtime.
6. Build, scan and sign images; record immutable digests; render Compose with production values.
7. Confirm approved dataset directory ownership/read-only permissions and leave Market/Scheme paths blank unless approval evidence exists.
8. Confirm managed backup success and create an approved pre-migration backup artifact.
9. Run `release_migrate.py` with migration credentials; verify head and audit triggers; remove migration credentials.
10. Start the stack behind Caddy; verify `/live`, `/ready`, authentication, logout, role navigation and agent governance.
11. Verify photo upload/retrieval, disk thresholds, logs/request IDs, error monitoring and backup alerts without real user data.
12. Run post-deploy smoke tests; observe error/latency metrics; obtain explicit go/no-go decision.
13. For rollback, redeploy prior image digests. Restore the database only under the separate DBA recovery procedure.

Recommended next milestone: **M23 container staging plus approved evidence-storage and authoritative-dataset onboarding**. M22 completion is not deployment authorization.
