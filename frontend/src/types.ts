export type FuelSource = 'ЦРТ' | 'АК'

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
    details: { fuel: DetailRow[]; ground: DetailRow[] }
    warnings: string[]
  }>
  total: Record<string, number>
  warnings: string[]
  data_snapshot: Record<string, number>
}

export interface DetailRow {
  service: string
  rate: number
  volume: number
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
