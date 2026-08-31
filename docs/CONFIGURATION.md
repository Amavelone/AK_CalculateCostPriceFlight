# Configuration and Reference Data

## Configuration

Configuration schema `2.0` owns typed calculation parameters, approved
aircraft multipliers and M1/M2/M3 scenario rates. Only registered variables,
functions and operations are accepted; arbitrary code, filesystem, HTTP and
database access are rejected.

Configuration versions are immutable. An administrator creates a draft, edits
the supported typed payload, validates, previews or compares it, then activates
or rolls back a version. Active Configuration cannot be edited directly.

## Reference Data

Reference Data independently versions Routes and Airport Other Costs. A route
has departure, arrival, distance and flight time; its canonical key is derived
and unique. Airport Other Costs use a unique airport and non-negative amount.
The v1 baseline contains 500 routes and 45 Airport Other Costs.

Reference drafts have the same validate, compare, preview, activate and rollback
lifecycle as Configuration. Reference activation is independent of Configuration
and does not change `data_revision`. The `/admin` UI edits only an in-memory
full draft payload before saving it; active records remain read-only.

## Live source and manual data

SRV and Fuel Registry are operational source configurations, not calculation
Configuration. Their directory, mask, active file and refresh status may be
managed through the source UI. Manual tariffs complement missing keys; imported
tariffs retain priority when a key conflicts.

Bulk CSV/XLSX Reference Data import, source/audit relocation into `/admin`, and
new calculation capabilities require a future release change.
