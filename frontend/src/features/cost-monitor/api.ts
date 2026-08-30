import type {
  ActiveConfiguration,
  CalculationOptions,
  CalculationRequest,
  CalculationResult,
  ConfigurationComparison,
  ConfigurationVersion,
  DraftResponse,
  ExportFormat,
  SourceConfig,
  Tariff,
} from './types'

async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  const response = await fetch(`/api${path}`, {
    credentials: 'include',
    headers: { 'Content-Type': 'application/json', ...(init.headers ?? {}) },
    ...init,
  })
  if (!response.ok) {
    const body = await response.json().catch(() => ({ detail: 'Не удалось выполнить операцию' }))
    throw new Error(body.detail ?? 'Не удалось выполнить операцию')
  }
  if (response.status === 204) return undefined as T
  return response.json() as Promise<T>
}

export const api = {
  getDraft: () => request<DraftResponse>('/drafts/current'),
  saveDraft: (calculation: CalculationRequest) =>
    request<DraftResponse>('/drafts/current', { method: 'PUT', body: JSON.stringify({ calculation }) }),
  calculate: (calculation: CalculationRequest, signal?: AbortSignal) =>
    request<CalculationResult>('/calculations', { method: 'POST', body: JSON.stringify(calculation), signal }),
  calculationOptions: () => request<CalculationOptions>('/calculation-options'),
  activeConfiguration: () => request<ActiveConfiguration>('/configuration/active'),
  configurationVersions: () => request<ConfigurationVersion[]>('/configuration/versions'),
  compareConfigurations: (leftVersion: number, rightVersion: number) =>
    request<ConfigurationComparison>(`/configuration/compare/${leftVersion}/${rightVersion}`),
  sources: () => request<SourceConfig[]>('/sources'),
  refreshSource: (id: string) => request<SourceConfig>(`/sources/${id}/refresh`, { method: 'POST' }),
  rawPreview: (id: string, sheet?: string) =>
    request<{ file: string; sheet: string; sheets: string[]; preview: Array<Record<string, unknown>> }>(
      `/sources/${id}/raw-preview${sheet ? `?sheet=${encodeURIComponent(sheet)}` : ''}`,
    ),
  refreshAll: () => request<{ sources: SourceConfig[] }>('/sources/refresh-all', { method: 'POST' }),
  updateSource: (id: string, directory: string, mask: string) =>
    request<SourceConfig>(`/sources/${id}`, { method: 'PUT', body: JSON.stringify({ directory, mask }) }),
  uploadSource: async (id: string, file: File): Promise<SourceConfig> => {
    const body = new FormData()
    body.append('file', file)
    const response = await fetch(`/api/sources/${id}/upload`, { method: 'POST', body, credentials: 'include' })
    if (!response.ok) {
      const error = await response.json().catch(() => ({ detail: 'Не удалось загрузить файл' }))
      throw new Error(error.detail)
    }
    return response.json() as Promise<SourceConfig>
  },
  tariffs: (search = '') => request<Tariff[]>(`/tariffs?search=${encodeURIComponent(search)}`),
  addManualTariff: (payload: Omit<Tariff, 'id' | 'source' | 'source_file' | 'conflict'>) =>
    request<Tariff>('/tariffs/manual', { method: 'POST', body: JSON.stringify(payload) }),
  deleteManualTariff: (id: string) => request<void>(`/tariffs/manual/${id}`, { method: 'DELETE' }),
  exportCalculation: async (format: ExportFormat, calculation: CalculationRequest): Promise<{ blob: Blob; filename: string }> => {
    const response = await fetch(`/api/exports/${format}`, {
      method: 'POST',
      credentials: 'include',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(calculation),
    })
    if (!response.ok) {
      const error = await response.json().catch(() => ({ detail: 'Не удалось сформировать выгрузку' }))
      throw new Error(error.detail ?? 'Не удалось сформировать выгрузку')
    }
    const disposition = response.headers.get('Content-Disposition') ?? ''
    const encodedName = disposition.match(/filename\*=UTF-8''([^;]+)/i)?.[1]
    const fallback = `Расчет_себестоимости.${format}`
    return { blob: await response.blob(), filename: encodedName ? decodeURIComponent(encodedName) : fallback }
  },
}
