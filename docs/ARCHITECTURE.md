# Architecture

## Scope

Cost Monitor v1 calculates the cost of ВВЛ flight legs. The backend is the only
owner of calculation rules; React renders typed API results and never recreates
formulas. The application release is defined by the repository-root `VERSION`
file.

```text
Calculation Configuration + Reference Data + Live Sources
                         -> Effective Context -> Calculation -> JSON/XLSX
```

## Runtime boundaries

- **Configuration** is immutable/versioned operational logic and approved
  aircraft/scenario values.
- **Reference Data** is immutable/versioned Routes and Airport Other Costs.
- **Live Sources** are only SRV and Fuel Registry. Their atomic refresh changes
  canonical tariffs/fuel prices and `data_revision`.
- A calculation identifies its `config_version`, `reference_version` and
  `data_revision`; Configuration/Reference activation does not change live data.

`refresh-all` stages both live sources and activates neither on a failure.
Imported tariff rows precede manual rows, preserving the parity-sensitive first
physical match for duplicate keys. Calculation rounding and M1/M2/M3 shape are
covered by the Excel golden-parity suite.

## Persistence and compatibility

JsonStore is a local atomic file adapter. Until it is replaced, production is
strictly one server, one process, one worker. The persistence contract isolates
the calculation module from a future SQL adapter.

Legacy Monitor Workbook parsing and its adapter are DEV compatibility tooling
only. They are not registered at startup, in production source UI, source
refresh, readiness, or the calculation lifecycle.

## Deferred boundaries

МВЛ, SQL Server, corporate authentication/RBAC, and Reference Data bulk import
are not part of v1. Authentication/RBAC is required before any network exposure
of administrative mutation endpoints.
