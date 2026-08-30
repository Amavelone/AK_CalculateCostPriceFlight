import { useState } from 'react'
import type { FormEvent } from 'react'
import { api } from '../api'
import { money } from '../formatting'
import type { Tariff } from '../types'

export function TariffsPage({ tariffs, search, onSearch, onDataChanged, onError, onNotice }: { tariffs: Tariff[]; search: string; onSearch: (value: string) => void; onDataChanged: () => Promise<void>; onError: (value: string | null) => void; onNotice: (value: string | null) => void }) {
  const [form, setForm] = useState({ airport: '', service: '', rate: '', unit: 'РУБ-ЕД', aircraft: '', note: '' })
  const [adding, setAdding] = useState(false)
  const submit = async (event: FormEvent) => {
    event.preventDefault()
    setAdding(true)
    onError(null)
    try {
      await api.addManualTariff({ ...form, airport: form.airport.toUpperCase(), service: form.service.toUpperCase(), rate: Number(form.rate), aircraft: form.aircraft.toUpperCase() })
      setForm({ airport: '', service: '', rate: '', unit: 'РУБ-ЕД', aircraft: '', note: '' })
      await onDataChanged()
      onNotice('Ручная услуга добавлена в единый справочник')
    } catch (caught) {
      onError(caught instanceof Error ? caught.message : 'Не удалось добавить ручную услугу')
    } finally {
      setAdding(false)
    }
  }
  const remove = async (tariff: Tariff) => {
    if (!window.confirm(`Удалить ручную услугу ${tariff.airport} — ${tariff.service}?`)) return
    try {
      await api.deleteManualTariff(tariff.id)
      await onDataChanged()
      onNotice('Ручная услуга удалена')
    } catch (caught) {
      onError(caught instanceof Error ? caught.message : 'Не удалось удалить услугу')
    }
  }
  return (
    <section className="page-stack">
      <div className="tariff-toolbar"><div><h2>Единый справочник услуг</h2><p>Импортированные тарифы и добавленные вручную значения хранятся вместе.</p></div><label className="search-field"><span>⌕</span><input value={search} onChange={(event) => onSearch(event.target.value)} placeholder="Аэропорт или услуга" /></label></div>
      <form className="manual-form" onSubmit={submit}>
        <div className="form-title"><b>Добавить вручную</b><span>Только для услуги, которой нет в распарсенных источниках.</span></div>
        <label><span>Аэропорт</span><input required maxLength={3} value={form.airport} placeholder="KJA" onChange={(event) => setForm({ ...form, airport: event.target.value.toUpperCase() })} /></label>
        <label className="service-field"><span>Услуга</span><input required value={form.service} placeholder="Например, ВОДА" onChange={(event) => setForm({ ...form, service: event.target.value.toUpperCase() })} /></label>
        <label><span>Ставка</span><input required type="number" min="0" step="0.01" value={form.rate} onChange={(event) => setForm({ ...form, rate: event.target.value })} /></label>
        <label><span>Ед. изм.</span><input value={form.unit} onChange={(event) => setForm({ ...form, unit: event.target.value })} /></label>
        <button className="button button-primary" disabled={adding}>{adding ? 'Добавляем…' : 'Добавить'}</button>
      </form>
      <div className="table-card"><div className="table-caption"><span>Найдено: {tariffs.length.toLocaleString('ru-RU')}</span>{tariffs.length > 200 && <span>Показаны первые 200 строк — уточните поиск.</span>}</div><div className="tariff-table-wrap"><table className="tariff-table"><thead><tr><th>Аэропорт</th><th>Услуга</th><th>Ставка</th><th>Ед. изм.</th><th>Происхождение</th><th /></tr></thead><tbody>{tariffs.slice(0, 200).map((tariff) => <tr key={tariff.id}><td><b>{tariff.airport}</b></td><td>{tariff.service}{tariff.conflict && <span className="conflict-badge">Конфликт</span>}</td><td>{money(tariff.rate)} ₽</td><td>{tariff.unit || '—'}</td><td><span className={`origin ${tariff.source}`}>{tariff.source === 'manual' ? 'Вручную' : tariff.source_file ?? 'Из файла'}</span></td><td>{tariff.source === 'manual' && <button className="delete-link" onClick={() => void remove(tariff)}>Удалить</button>}</td></tr>)}</tbody></table></div></div>
    </section>
  )
}
