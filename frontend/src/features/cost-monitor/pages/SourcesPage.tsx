import { useState } from 'react'
import { api } from '../api'
import { timeText } from '../formatting'
import type { SourceConfig } from '../types'

interface SourcesPageProps {
  sources: SourceConfig[]
  busySource: string | null
  onRefreshOne: (id: string) => void
  onRefreshAll: () => void
  onUpload: (source: SourceConfig, file: File) => void
}

export function SourcesPage({ sources, busySource, onRefreshOne, onRefreshAll, onUpload }: SourcesPageProps) {
  return (
    <section className="page-stack">
      <div className="source-intro">
        <div><h2>Подключенные источники</h2><p>Загрузите новую выгрузку в настроенную папку или обновите данные из уже размещенных файлов.</p></div>
        <button className="button button-primary" onClick={onRefreshAll} disabled={busySource !== null}>{busySource === 'all' ? 'Обновляем…' : '↻ Обновить все'}</button>
      </div>
      <div className="source-grid">
        {sources.map((source) => <SourceCard key={source.id} source={source} busySource={busySource} onRefreshOne={onRefreshOne} onUpload={onUpload} />)}
      </div>
    </section>
  )
}

function SourceCard({ source, busySource, onRefreshOne, onUpload }: { source: SourceConfig; busySource: string | null; onRefreshOne: (id: string) => void; onUpload: (source: SourceConfig, file: File) => void }) {
  const [raw, setRaw] = useState<Array<Record<string, unknown>> | null>(null)
  const [rawFile, setRawFile] = useState<string | null>(null)
  const [rawSheet, setRawSheet] = useState<string | null>(null)
  const [rawSheets, setRawSheets] = useState<string[]>([])
  const [rawError, setRawError] = useState<string | null>(null)
  const [loadingRaw, setLoadingRaw] = useState(false)
  const loadRaw = async (sheet?: string) => {
    if (raw && (!sheet || sheet === rawSheet)) return
    setLoadingRaw(true)
    try {
      const response = await api.rawPreview(source.id, sheet)
      setRaw(response.preview)
      setRawFile(response.file)
      setRawSheet(response.sheet)
      setRawSheets(response.sheets)
      setRawError(null)
    } catch (caught) {
      setRawError(caught instanceof Error ? caught.message : 'Не удалось открыть исходный файл')
    } finally {
      setLoadingRaw(false)
    }
  }
  return <article className="source-card">
    <div className="source-card-head"><div className="source-icon">{source.id === 'fuel_registry' ? '◒' : source.id === 'monitor_workbook' ? '▦' : '↗'}</div><StatusBadge status={source.last_status} /></div>
    <h2>{source.label}</h2><p>{source.description}</p>
    <div className="source-details"><span>Файл</span><b>{source.last_file ?? source.mask}</b><span>Последнее обновление</span><b>{timeText(source.last_updated)}</b><span>Строк загружено</span><b>{source.rows_loaded.toLocaleString('ru-RU')}</b></div>
    {source.last_error && <div className="source-error">{source.last_error}</div>}
    {source.last_note && <div className="source-note">{source.last_note}</div>}
    <div className="source-actions">
      <label className="button button-secondary file-button">Загрузить файл<input type="file" accept=".xlsx" onChange={(event) => { const file = event.target.files?.[0]; if (file) void onUpload(source, file); event.currentTarget.value = '' }} /></label>
      <button className="button button-quiet" disabled={busySource !== null} onClick={() => onRefreshOne(source.id)}>{busySource === source.id ? 'Обновляем…' : 'Обновить'}</button>
    </div>
    <details className="preview" onToggle={(event) => { if ((event.currentTarget as HTMLDetailsElement).open) void loadRaw() }}><summary>{loadingRaw ? 'Открываем исходный файл…' : 'Посмотреть исходные строки'}</summary>{rawError && <div className="source-error">{rawError}</div>}{raw && <><div className="preview-file"><span>{rawFile}</span>{rawSheets.length > 1 && <select aria-label="Лист книги" value={rawSheet ?? ''} onChange={(event) => void loadRaw(event.target.value)}>{rawSheets.map((sheet) => <option key={sheet}>{sheet}</option>)}</select>}</div><PreviewTable rows={raw} /></>}</details>
    {source.preview.length > 0 && <details className="preview"><summary>Посмотреть результат парсинга</summary><PreviewTable rows={source.preview} /></details>}
  </article>
}

function StatusBadge({ status }: { status: SourceConfig['last_status'] }) {
  const labels: Record<SourceConfig['last_status'], string> = { ready: 'Готов', uploaded: 'Загружен', not_updated: 'Не обновлялся', error: 'Ошибка' }
  return <span className={`status-badge ${status}`}>{labels[status]}</span>
}

function PreviewTable({ rows }: { rows: Array<Record<string, unknown>> }) {
  const columns = Object.keys(rows[0] ?? {}).slice(0, 4)
  return <div className="preview-table-wrap"><table className="preview-table"><thead><tr>{columns.map((column) => <th key={column}>{column}</th>)}</tr></thead><tbody>{rows.slice(0, 5).map((row, index) => <tr key={index}>{columns.map((column) => <td key={column}>{String(row[column] ?? '—')}</td>)}</tr>)}</tbody></table></div>
}
