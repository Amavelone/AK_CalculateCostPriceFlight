export type FuelSource = 'ЦРТ' | 'АК'
export type ExportFormat = 'json' | 'xlsx'
export type ConfigurationState = 'active' | 'inactive' | 'draft'
export type JsonValue = string | number | boolean | null | JsonValue[] | { [key: string]: JsonValue }

export interface LegInput {
  id: string
  departure: string
  arrival: string
  aircraft: string
  passengers: number
}

export interface CalculationSettings {
  scenario: string
  fuel_source: FuelSource
  techstop_leg_id: string | null
  catering: boolean
  show_details: boolean
}

export interface CalculationRequest {
  legs: LegInput[]
  settings: CalculationSettings
}

export interface CalculationResult {
  calculated_at: string
  status: 'complete' | 'degraded'
  diagnostics: CalculationDiagnostic[]
  legs: Array<{
    id: string
    route: string
    departure: string
    arrival: string
    aircraft: string
    passengers: number
    flight_time: number
    distance: number
    fuel_tons: number
    line_type: string
    is_techstop: boolean
    components: Record<string, number>
    totals: Record<string, number>
    details: { fuel: DetailRow[]; ground: DetailRow[]; ano: DetailRow[]; catering: DetailRow[]; vat: DetailRow[] }
    warnings: string[]
    status: 'complete' | 'degraded'
    diagnostics: CalculationDiagnostic[]
  }>
  total: Record<string, number>
  warnings: string[]
  data_snapshot: {
    revision: number
    tariffs: number
    manual_tariffs: number
    fuel_prices: number
    routes: number
    reference_version: number
  }
  config_version: number
  configuration_state: 'active' | 'draft'
  reference_version: number
  reference_state: 'active' | 'draft'
  trace: CalculationTrace
}

export interface CalculationTraceStep {
  stage: 'input' | 'lookup' | 'parameters' | 'operation' | 'result'
  component: string
  operation: string | null
  values: Record<string, JsonValue>
}

export interface CalculationTrace {
  config_version: number
  configuration_state: 'active' | 'draft'
  data_revision: number
  reference_version: number
  reference_state: 'active' | 'draft'
  legs: Array<{ leg_id: string; steps: CalculationTraceStep[] }>
}

export interface CostMonitorConfiguration {
  schema_version: '2.0'
  fuel: { consumption_tons_per_hour: number }
  ano: { route_rate_per_100_km: number }
  catering: { base_units: number; base_unit_rate: number; passenger_surcharge: number }
  vat: { rate: number; airports: string[] }
  ground: {
    split_divisor: number
    stairs_units: number
    telebridge_minutes: number
    transport_passenger_block: number
    fire_truck_rate: number
  }
  operations: {
    ano: StepOperations
    catering: StepOperations
    vat: StepOperations
  }
  overrides: {
    aircraft_multipliers: Record<string, number>
    scenario_rates: Record<string, Record<string, [number, number, number]>>
  }
}

export type ValueReference =
  | { kind: 'constant'; value: string | number | boolean | string[] }
  | { kind: 'variable'; name: string }
  | { kind: 'parameter'; path: string }
  | { kind: 'lookup'; name: string; arguments: Record<string, Exclude<ValueReference, { kind: 'lookup' }>> }

export interface OperationAction {
  operation: 'add' | 'subtract' | 'multiply' | 'divide' | 'round'
  operand: ValueReference | null
  digits: number | null
}

export interface OperationCondition {
  any_of: Array<{
    all_of: Array<{
      left: ValueReference
      operator: 'eq' | 'ne' | 'gt' | 'gte' | 'lt' | 'lte' | 'in' | 'not_in'
      right: ValueReference
    }>
  }>
}

export interface OperationPart {
  id: string
  label: string
  initial: ValueReference
  operations: OperationAction[]
  condition: OperationCondition | null
  detail_service: string
}

export interface StepOperations {
  parts: OperationPart[]
  aggregation: 'sum'
}

export interface ConfigurationVersion {
  version: number
  state: 'active' | 'inactive'
  created_at: string
  activated_at: string | null
  validation_status: 'valid'
  is_default: boolean
  configuration?: CostMonitorConfiguration | null
}

export interface ActiveConfiguration extends ConfigurationVersion {
  state: 'active'
  configuration: CostMonitorConfiguration
}

export interface ConfigurationReference {
  version: number
  state: ConfigurationState
  created_at: string
  activated_at: string | null
  updated_at: string | null
  base_version: number | null
  validation_status: 'valid'
  is_default: boolean
}

export interface ConfigurationComparison {
  left: ConfigurationReference
  right: ConfigurationReference
  changes: Array<{
    path: string
    before: JsonValue
    after: JsonValue
    kind: 'parameter_changed' | 'operation_added' | 'operation_removed' | 'operation_changed' | 'operation_reordered' | 'override_changed'
    summary: string
    presentation?: { label: string; group: string; unit: string | null; where_used: string[] } | null
  }>
}

export interface ConfigurationDraft {
  version: number
  state: 'draft'
  base_version: number
  created_at: string
  updated_at: string
  validated_at: string | null
  validation_status: 'valid'
  configuration: CostMonitorConfiguration
}

export interface ConfigurationCapabilities {
  schema_version: '2.0'
  parameters: string[]
  variables: Array<{ name: string; value_type: string; description: string; arguments: string[] }>
  operations: Array<{ name: string; value_type: null; description: string; arguments: string[] }>
  lookups: Array<{ name: string; value_type: null; description: string; arguments: string[] }>
  condition_operators: string[]
}

export interface ConfigurationPresentationParameter {
  id: string
  label: string
  description: string
  group: string
  unit: string
  editable: boolean
  advanced: boolean
  bounds: Record<string, number>
  where_used: string[]
}

export interface ConfigurationPresentation {
  groups: Array<{ id: string; label: string; description: string }>
  parameters: ConfigurationPresentationParameter[]
  advanced: { operations: { enabled: boolean; steps: string[] }; lookups: { enabled: boolean }; conditions: { enabled: boolean } }
}

export interface ConfigurationPreviewComparison {
  active: CalculationResult
  draft: CalculationResult
  difference: { total: Record<string, number>; legs: Record<string, Record<string, number>> }
}

export interface ReferenceRoute {
  departure: string
  arrival: string
  distance: number
  flight_time: number
  source_row: number | null
}

export interface AirportOtherCost {
  airport: string
  amount: number
}

export interface CostMonitorReferenceData {
  schema_version: '1.0'
  routes: ReferenceRoute[]
  airport_other_costs: AirportOtherCost[]
}

export interface ReferenceDataVersion {
  version: number
  state: 'active' | 'inactive'
  created_at: string
  activated_at: string | null
  validation_status: 'valid'
  reference_data?: CostMonitorReferenceData | null
}

export interface ActiveReferenceData extends ReferenceDataVersion {
  state: 'active'
  reference_data: CostMonitorReferenceData
}

export interface ReferenceDataDraft {
  version: number
  state: 'draft'
  base_version: number
  created_at: string
  updated_at: string
  validated_at: string | null
  validation_status: 'valid'
  reference_data: CostMonitorReferenceData
}

export interface ReferenceDataVersionReference {
  version: number
  state: 'active' | 'inactive' | 'draft'
  created_at: string
  activated_at: string | null
  updated_at: string | null
  base_version: number | null
  validation_status: 'valid'
}

export interface ReferenceDataComparison {
  left: ReferenceDataVersionReference
  right: ReferenceDataVersionReference
  changes: Array<{
    path: string
    before: JsonValue
    after: JsonValue
    kind: 'record_added' | 'record_removed' | 'record_changed'
    summary: string
  }>
}

export interface ReferenceDataPreviewComparison {
  active: CalculationResult
  draft: CalculationResult
  difference: { total: Record<string, number>; legs: Record<string, Record<string, number>> }
}

export interface CalculationDiagnostic {
  code: string
  severity: 'warning'
  component: string
  reference: string | null
  message: string
}

export interface DetailRow {
  airport?: string
  service: string
  rate: number
  volume: number
  divisor?: number
  amount: number
}

export interface DraftResponse {
  calculation: CalculationRequest
  updated_at: string | null
}

export interface CalculationOptions {
  scenarios: string[]
  aircraft: string[]
}

export interface SourceConfig {
  id: 'srv' | 'fuel_registry'
  label: string
  description: string
  directory: string
  mask: string
  parser: string
  last_status: 'not_updated' | 'uploaded' | 'ready' | 'error'
  last_file: string | null
  active_file?: string | null
  uploaded_file?: string | null
  last_updated: string | null
  last_error: string | null
  last_note?: string | null
  rows_read: number
  rows_loaded: number
  preview: Array<Record<string, unknown>>
}

export interface Tariff {
  id: string
  airport: string
  service: string
  rate: number
  unit: string
  aircraft: string
  source: 'file' | 'manual'
  source_file: string | null
  conflict: boolean
  note?: string
}
