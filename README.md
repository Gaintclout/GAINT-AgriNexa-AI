# GAINT AgriNexa AI

GAINT AgriNexa AI is a development-stage agricultural intelligence platform with a FastAPI service, React/Vite web application, PostgreSQL/PostGIS persistence, role-based authorization, parcel registry, offline-first field verification, and SCIM satellite metadata and analysis tools.

## Run locally

Install the API dependencies (including PostGIS and raster processing support):

```powershell
cd services\api
python -m pip install -r requirements-sprint1-dev.txt
$projData = python -c "import pyproj; print(pyproj.datadir.get_data_dir())"
$env:PROJ_DATA = $projData
$env:PROJ_LIB = $projData
Remove-Item Env:GDAL_DATA -ErrorAction SilentlyContinue
python -m pytest -q
.\tools\run_dev.ps1 -Reload
```
cd "D:\GAINT AI Agri\apps\web\GAINT-AgriNexa-AI"

.\.venv\Scripts\Activate.ps1

python -m uvicorn app.main:app --host 127.0.0.1 --port 8001 --reload

For local raster tests, point PROJ to the data bundled with the installed PyProj package, not an unrelated PostgreSQL/PostGIS installation. The commands above set this for the current PowerShell session.

Run the web client:

```powershell
cd apps\web
npm install
npm test
npx playwright install chromium
npm run test:browser
npm run build
npm run dev
```

Create `services\api\.env` from an authorized local configuration before starting the API. Verify that its database target is a disposable database approved for this run; do not point it at the protected `agrinexa` database or reuse exposed credentials. The development launcher generates an ephemeral JWT secret when none is configured and defaults private photo storage to `%LOCALAPPDATA%\GAINT AI Agri\private-photos`; manual Uvicorn launches must configure both explicitly. The API command uses Uvicorn's `--env-file .env` option to load that file without overriding variables already set in the process environment. Set `VITE_API_BASE_URL` when the API is not at `http://localhost:8000`. API startup does not apply migrations automatically.

The Playwright browser suite starts a temporary local Vite server and intercepts all API requests with synthetic fixtures. It verifies browser UI, IndexedDB offline persistence, role-isolated views, mocked evidence synchronization/review, and responsive layouts without starting the API or connecting to a database. These mocked browser results are not live UAT evidence. See [browser acceptance](docs/BROWSER_ACCEPTANCE.md) and [submission readiness](docs/submission-readiness.md).

The browser client always uses same-origin paths. During development, Vite forwards `/api`, health/readiness, and OpenAPI requests to `VITE_PROXY_TARGET` (configured in `apps\web\.env.local`). Use the backend listener address reachable from both local and LAN clients; this workspace currently uses `http://192.168.0.102:8001`. Do not set a browser-visible API base URL: a loopback URL in browser code breaks access from another LAN device. The proxy preserves the browser host/origin, so both `http://localhost:5173` and the machine's LAN address use the same authenticated route without permissive CORS.

The development launcher loads `.env`, binds the API to `0.0.0.0:8001`, and creates an ephemeral in-memory JWT secret when `AGRINEXA_JWT_SECRET` has not been supplied. Do not start a second Uvicorn process on `127.0.0.1:8001`; a more-specific loopback listener can shadow the configured server for local proxy targets.

The tracked `.env.example` contains placeholders only and targets `agrinexa_uat_test`. Never use the protected `agrinexa` database for development or tests. Database connection failures are returned as a generic service-unavailable response and are logged without connection strings or SQL parameters.

## Implemented workflows

- Farmer registration and login, protected role-aware workspaces, and ownership-scoped parcel reads.
- Parcel and village registry, owner assignment for Admin/GIS Operator, and GIS map views.
- Field Verifier offline evidence capture, private photo submission, retry-safe sync, and Officer/Admin review.
- Satellite catalogue metadata discovery, scene assessment, spectral indices, parcel sample summaries, SCIM job metadata, and offline raster processing tools.
- Role-specific dashboards and responsive layouts.

## Explicitly not production-ready

- The eight AI agents are listed for governance visibility only; agent execution is not implemented or enabled.
- Governed learning is not active. There is no approved feedback store, consent/retention workflow, or model promotion pipeline.
- SCIM catalogue discovery returns metadata; it does not establish parcel-level scene provenance or automatically ingest imagery. Worker execution and real-scene validation remain gated.
- Farmer crop recommendations, market/scheme integrations, and a deployed mobile application are not established by the current code.
- Browser acceptance, disposable PostGIS integration, real-scene validation, operational monitoring, and deployment sign-off must be completed separately.

See the [module completion matrix](docs/sprint1-status.md), [API inventory](docs/api-inventory.md), and [submission readiness report](docs/submission-readiness.md) for verified scope and open gates.

Use only a disposable database named `agrinexa_uat_test` for UAT writes. Never point tests or local tools at the existing `agrinexa` database. Migrations and test-user provisioning are manual; this project does not create test accounts automatically. The proposed restricted runtime-role procedure is review-only and must not be executed without explicit database-owner approval: [UAT runtime role procedure](docs/uat-runtime-role-procedure.sql).
