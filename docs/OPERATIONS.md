# Operations

## Requirements and environment

CI validates Python 3.12, Node 22 and pnpm 11.19.0. Production requires explicit
`APP_ENV=production`, `MONITOR_DATA_DIRECTORY`, `MONITOR_SOURCE_DIRECTORY`,
`HOST`, `PORT` and `LOG_LEVEL`. Data and source directories must exist, be
absolute and be readable/writable. `.env.example` lists non-secret settings.

Development defaults are repository-local. Production never falls back to a
developer Downloads directory.

## Build and start

```powershell
pnpm --dir frontend install --frozen-lockfile
pnpm --dir frontend build
Push-Location backend
..\.venv\Scripts\python -m app
Pop-Location
```

Production serves `/` and `/admin` from `frontend/dist`; do not use `--reload`,
`pnpm dev`, or more than one worker while JsonStore is active.

`/api/health` confirms that the process responds. `/api/ready` additionally
requires a readable store, valid active Configuration and Reference Data, and
initialized SRV/Fuel Registry data. It returns 503 until that state exists.

## Backup, recovery and observability

Stop the sole application process before backup or restore. Copy the complete
configured data directory (including `store.json`), required active source files
and deployment settings stored outside Git. Restore the same consistent set,
start one worker and verify `/api/ready`; this preserves versions, audit history
and live data revision.

Request logs use text `key=value` fields with timestamp, level, endpoint, error,
Configuration version, Reference Data version and data revision. Request bodies,
cookies and credentials are not logged.

## Security

Production is same-origin and draft cookies are Secure, HttpOnly and SameSite
Lax; HTTPS terminates before the application. This is not authorization.
Corporate authentication/RBAC is absent and is a P0 blocker for network
deployment, especially for `/admin` mutation APIs.
