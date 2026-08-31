# Calculation Baseline

## Supported v1 behavior

Cost Monitor accepts any number of ВВЛ flight legs. Each leg contains departure,
arrival, aircraft and passenger count; one leg may be selected as a technical
stop. The calculation request chooses scenario, fuel source (`ЦРТ` or `АК`) and
whether passenger catering is enabled.

For each leg the backend resolves Route and then calculates fuel, ground costs,
ANO, catering, VAT and M1/M2/M3. The result is the sum of all leg totals and
includes diagnostics, details and provenance versions.

- Fuel consumption, aircraft multipliers and scenario rates are active
  Configuration values.
- Routes and Airport Other Costs are active Reference Data values.
- SRV tariffs and Fuel Registry prices are live data.
- With fuel source `АК`, the Fuel Registry price for the departure airport is
  used; otherwise the parity-sensitive ground tariff matrix supplies fuel costs.

## Parity rules

The backend preserves physical first-match tariff lookup order, approved rounding
rules and the M1/M2/M3 result contract. Imported tariffs precede manual tariffs;
manual values never override an imported duplicate. Missing route, tariff or
fuel data is reported in diagnostics rather than silently inventing a value.

Any calculation-rule change requires an explicit business decision and updates
to the Excel golden-parity fixtures/tests. Legacy workbook parsing is retained
only for DEV compatibility and migration tests, never as production input.
