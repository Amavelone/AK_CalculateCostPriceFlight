# Cost Monitor v1.0.0

Cost Monitor calculates the cost of flight legs for operational users. It
combines approved calculation Configuration, versioned reference data and live
SRV/Fuel Registry sources, then returns traceable M1/M2/M3 results and JSON/XLSX
exports.

## Supported v1 scope

- ВВЛ flight legs, any count of legs, one optional technical stop, `ЦРТ`/`АК`
  fuel sources and optional passenger catering.
- Versioned Configuration and Reference Data with draft/validate/preview/
  compare/activate/rollback lifecycle in `/admin`.
- SRV and Fuel Registry production sources with atomic `refresh-all`.
- Reference routes, Airport Other Costs and manual tariffs; JSON/XLSX exports.

МВЛ is out of scope for v1. Legacy Monitor Workbook is DEV compatibility tooling
only and is never a production runtime source.

## Architecture and documents

```text
Calculation Configuration + Reference Data + Live Sources
                         -> Effective Context -> Calculation
```

- [Architecture](docs/ARCHITECTURE.md)
- [Calculation baseline](docs/CALCULATION.md)
- [Configuration and Reference Data](docs/CONFIGURATION.md)
- [Operations and recovery](docs/OPERATIONS.md)

## Requirements and environment

Use Python 3.12, Node 22 and pnpm 11.19.0. `.env.example` lists all non-secret
environment variables. Production requires explicit `APP_ENV=production`, data
and source directories, host, port and log level; it never falls back to a
developer path.

## Development start

```powershell
py -m venv .venv
.\.venv\Scripts\python -m pip install -r backend\requirements.txt
Push-Location frontend
pnpm install --frozen-lockfile
pnpm dev
Pop-Location
.\.venv\Scripts\python -m uvicorn app.main:app --app-dir backend --reload --port 8000
```

Open `http://localhost:5173`. Set `MONITOR_SOURCE_DIRECTORY` only when local
source workbooks are available.

## Test and build

```powershell
$env:PYTHONPATH = (Resolve-Path .\backend).Path
.\.venv\Scripts\python -m unittest discover -s .\backend\tests -v
.\.venv\Scripts\ruff check backend
Push-Location frontend
pnpm install --frozen-lockfile
pnpm exec tsc -b
pnpm exec vite build
Pop-Location
```

The GitHub Actions workflow runs these release gates on push and pull request.

## Production start and routes

Build the frontend, set every production variable from `.env.example`, then run:

```powershell
Push-Location backend
..\.venv\Scripts\python -m app
Pop-Location
```

FastAPI serves `/` and `/admin` from `frontend/dist`. Use no reload and exactly
one worker while JsonStore is the persistence adapter. Routes are `/`, `/admin`,
`/api/health`, and `/api/ready`.

`/api/ready` remains 503 until the store, active Configuration, active Reference
Data and both production sources are initialized. Backup/restore, logging and
source-operation details are in [Operations](docs/OPERATIONS.md).

## Administration and limitations

`/admin` manages Configuration and Reference Data drafts; active versions are
read-only. Source setup and manual tariffs remain in the normal application.

JsonStore is limited to one server, one process and one worker until SQL Server.
Corporate authentication/RBAC is absent: this is a P0 blocker for network
deployment, and `/admin` route separation is not an authorization boundary.
