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
  data_snapshot: Record<string, number>
  config_version: number
  configuration_state: 'active' | 'draft'
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
  legs: Array<{ leg_id: string; steps: CalculationTraceStep[] }>
}

export interface CostMonitorConfiguration {
  schema_version: '1.0'
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
  initial_data: {
    aircraft_multipliers: Record<string, number>
    scenario_rates: Record<string, Record<string, [number, number, number]>>
  }
  source_bindings: Array<{
    id: 'srv' | 'fuel_registry' | 'monitor_workbook'
    label: string
    description: string
    parser: 'srv_tariffs' | 'fuel_registry' | 'monitor_workbook'
    default_mask: string
  }>
}

export interface ConfigurationVersion {
  version: number
  state: 'active' | 'inactive'
  created_at: string
  activated_at: string | null
  validation_status: 'valid'
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
}

export interface ConfigurationComparison {
  left: ConfigurationReference
  right: ConfigurationReference
  changes: Array<{ path: string; before: JsonValue; after: JsonValue }>
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
  id: string
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
