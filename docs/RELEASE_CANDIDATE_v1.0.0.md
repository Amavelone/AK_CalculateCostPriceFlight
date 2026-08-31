# Release Candidate v1.0.0

## Release identity

- Branch: `release/v1.0.0`
- Application version: `1.0.0` from the repository-root `VERSION` file.
- Configuration baseline: immutable active Configuration v1.
- Reference Data baseline: immutable active Reference Data v1 (500 routes and
  45 Airport Other Costs).
- Live source model: SRV and Fuel Registry only; `refresh-all` stages both and
  atomically preserves the prior canonical dataset on a failure.

## Validation

The CI workflow runs backend regression/golden-parity/API/configuration/source/
reference-data tests, Ruff, frontend strict typecheck, and frontend production
build. The release validation matrix is covered by the corresponding unit,
contract and parity suites, including config/reference lifecycle, exports,
source-refresh failure, `/admin`, `/api/health`, and `/api/ready`.

Production startup builds `frontend/dist`, serves `/` and `/admin` from FastAPI,
uses no reload and exactly one worker while JsonStore remains the persistence
adapter. `/api/ready` requires a readable store, active Configuration/Reference
Data, and initialized SRV/Fuel Registry canonical data.

## Known deployment limitations and risks

- JsonStore is limited to one server, one process, one worker until SQL Server.
- Corporate authentication/RBAC is not implemented. This is a P0 blocker for
  network deployment: `/admin` and same-origin routing are not authorization.
- Production requires explicit writable data/source directories, backup/restore
  discipline, HTTPS termination, and source initialization before readiness is
  green.
- v1 remains ВВЛ-only; Legacy Monitor Workbook is DEV compatibility tooling;
  Reference Data bulk import and MВЛ remain deferred.

No merge, tag, GitHub Release, or deployment is authorized by this candidate.
