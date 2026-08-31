import { useEffect, useMemo, useState } from 'react'
import type {
  ActiveReferenceData,
  AirportOtherCost,
  CalculationRequest,
  ReferenceDataComparison,
  ReferenceDataDraft,
  ReferenceDataPreviewComparison,
  ReferenceDataVersion,
  ReferenceRoute,
} from '../types'

interface ReferenceDataAdminProps {
  active: ActiveReferenceData | null
  versions: ReferenceDataVersion[]
  draft: ReferenceDataDraft | null
  comparison: ReferenceDataComparison | null
  preview: ReferenceDataPreviewComparison | null
  calculation: CalculationRequest
  busy: string | null
  onReferenceDataChange: (referenceData: ReferenceDataDraft['reference_data']) => void
  onCreateDraft: () => void
  onSave: () => void
  onValidate: () => void
  onPreview: () => void
  onActivate: () => void
  onRollback: (version: number) => void
  onCompare: (left: number, right: number) => void
}

const number = new Intl.NumberFormat('ru-RU', { maximumFractionDigits: 3 })
const dateTime = (value: string | null) => value ? new Date(value).toLocaleString('ru-RU') : '—'
const valueText = (value: unknown) => value === undefined ? '—' : JSON.stringify(value, null, 2)

export function ReferenceDataAdmin(props: ReferenceDataAdminProps) {
  const { active, versions, draft, comparison, preview, calculation, busy } = props
  const [routeSearch, setRouteSearch] = useState('')
  const [otherCostSearch, setOtherCostSearch] = useState('')
  const [leftVersion, setLeftVersion] = useState<number | null>(null)
  const [rightVersion, setRightVersion] = useState<number | null>(null)
  const referenceData = draft?.reference_data ?? active?.reference_data ?? null
  const editable = Boolean(draft && referenceData)
  const activeVersion = active?.version
  const orderedVersions = [...versions].sort((left, right) => right.version - left.version)
  const selectableVersions = draft ? [draft.version, ...orderedVersions.map((version) => version.version)] : orderedVersions.map((version) => version.version)

  useEffect(() => {
    if (selectableVersions.length) {
      if (draft && activeVersion !== undefined) {
        setLeftVersion((current) => current === draft.version ? activeVersion : current ?? activeVersion)
        setRightVersion(draft.version)
      } else {
        setLeftVersion((current) => current ?? selectableVersions[1] ?? selectableVersions[0])
        setRightVersion((current) => current ?? selectableVersions[0])
      }
    }
  }, [activeVersion, draft, selectableVersions.length, versions.length])

  const visibleRoutes = useMemo(() => {
    const phrase = routeSearch.trim().toUpperCase()
    return (referenceData?.routes ?? []).map((route, index) => ({ route, index })).filter(({ route }) => {
      return !phrase || route.departure.includes(phrase) || route.arrival.includes(phrase)
    })
  }, [referenceData?.routes, routeSearch])
  const visibleOtherCosts = useMemo(() => {
    const phrase = otherCostSearch.trim().toUpperCase()
    return (referenceData?.airport_other_costs ?? []).map((item, index) => ({ item, index })).filter(({ item }) => {
      return !phrase || item.airport.includes(phrase)
    })
  }, [referenceData?.airport_other_costs, otherCostSearch])

  const changeRoutes = (routes: ReferenceRoute[]) => {
    if (!draft || !referenceData) return
    props.onReferenceDataChange({ ...referenceData, routes })
  }
  const changeOtherCosts = (airportOtherCosts: AirportOtherCost[]) => {
    if (!draft || !referenceData) return
    props.onReferenceDataChange({ ...referenceData, airport_other_costs: airportOtherCosts })
  }
  const updateRoute = (index: number, patch: Partial<ReferenceRoute>) => {
    if (!referenceData) return
    changeRoutes(referenceData.routes.map((route, routeIndex) => routeIndex === index ? { ...route, ...patch } : route))
  }
  const updateOtherCost = (index: number, patch: Partial<AirportOtherCost>) => {
    if (!referenceData) return
    changeOtherCosts(referenceData.airport_other_costs.map((item, itemIndex) => itemIndex === index ? { ...item, ...patch } : item))
  }

  if (!active || !referenceData) return <section className="admin-card"><div className="admin-empty">Reference Data недоступны.</div></section>

  return <>
    <section className="admin-card reference-data-heading">
      <div className="section-heading"><div><h2>Reference Data</h2><p>Routes и Airport Other Costs. Active version immutable; запись доступна только в draft.</p></div><span className="admin-version-chip">active v{active.version}</span></div>
      <div className="admin-summary-grid reference-summary-grid">
        <article className="admin-summary-card"><span>Routes</span><b>{active.reference_data.routes.length}</b><small>active v{active.version}</small></article>
        <article className="admin-summary-card"><span>Other costs</span><b>{active.reference_data.airport_other_costs.length}</b><small>airport-level records</small></article>
        <article className="admin-summary-card"><span>Draft</span><b>{draft ? `v${draft.version}` : '—'}</b><small>{draft ? draft.validation_status : 'не создан'}</small></article>
        <article className="admin-summary-card"><span>Control route</span><b>{calculation.legs[0]?.departure || '—'} → {calculation.legs[0]?.arrival || '—'}</b><small>used for preview</small></article>
      </div>
    </section>

    <section className="admin-toolbar admin-card reference-lifecycle-toolbar"><div><b>Reference lifecycle</b><p>Изменения сохраняются полным typed draft payload; Git baseline не меняется.</p></div><div className="admin-actions">
      <button className="button" disabled={Boolean(draft) || Boolean(busy)} onClick={props.onCreateDraft}>Create Draft</button>
      <button className="button button-secondary" disabled={!editable || Boolean(busy)} onClick={props.onSave}>Save</button>
      <button className="button button-secondary" disabled={!editable || Boolean(busy)} onClick={props.onValidate}>Validate</button>
      <button className="button button-secondary" disabled={!editable || Boolean(busy)} onClick={props.onPreview}>Preview</button>
      <button className="button" disabled={!editable || Boolean(busy)} onClick={props.onActivate}>Activate</button>
    </div></section>

    <section className="admin-card reference-catalog-card">
      <div className="section-heading"><div><h2>Routes</h2><p>Departure, Arrival, Distance и Flight Time.</p></div><div className="reference-catalog-actions"><label className="search-field"><span>⌕</span><input value={routeSearch} onChange={(event) => setRouteSearch(event.target.value.toUpperCase())} placeholder="Search DEP or ARR" /></label><button className="button button-secondary" disabled={!editable || Boolean(busy)} onClick={() => changeRoutes([...referenceData.routes, { departure: '', arrival: '', distance: 0, flight_time: 0, source_row: null }])}>Add route</button></div></div>
      {!editable && <div className="admin-empty">Создайте draft, чтобы изменить Reference Data.</div>}
      <div className="admin-table-wrap reference-table-wrap"><table className="admin-table reference-data-table"><thead><tr><th>Departure</th><th>Arrival</th><th>Distance</th><th>Flight Time</th><th>Action</th></tr></thead><tbody>{visibleRoutes.map(({ route, index }) => <tr key={`${route.departure}-${route.arrival}-${index}`}><td><input aria-label={`Route ${index + 1} departure`} value={route.departure} disabled={!editable || Boolean(busy)} onChange={(event) => updateRoute(index, { departure: event.target.value.toUpperCase() })} /></td><td><input aria-label={`Route ${index + 1} arrival`} value={route.arrival} disabled={!editable || Boolean(busy)} onChange={(event) => updateRoute(index, { arrival: event.target.value.toUpperCase() })} /></td><td><input aria-label={`Route ${index + 1} distance`} type="number" min="0" step="0.001" value={route.distance} disabled={!editable || Boolean(busy)} onChange={(event) => updateRoute(index, { distance: Number(event.target.value) })} /></td><td><input aria-label={`Route ${index + 1} flight time`} type="number" min="0" step="0.001" value={route.flight_time} disabled={!editable || Boolean(busy)} onChange={(event) => updateRoute(index, { flight_time: Number(event.target.value) })} /></td><td><button disabled={!editable || Boolean(busy)} onClick={() => changeRoutes(referenceData.routes.filter((_, routeIndex) => routeIndex !== index))}>Delete</button></td></tr>)}</tbody></table></div>
      {visibleRoutes.length === 0 && <div className="admin-empty">Routes не найдены.</div>}
    </section>

    <section className="admin-card reference-catalog-card">
      <div className="section-heading"><div><h2>Airport Other Costs</h2><p>Нефиксированные airport identifiers, включая legacy opaque codes, сохраняются без IATA-only ограничения.</p></div><div className="reference-catalog-actions"><label className="search-field"><span>⌕</span><input value={otherCostSearch} onChange={(event) => setOtherCostSearch(event.target.value.toUpperCase())} placeholder="Search airport" /></label><button className="button button-secondary" disabled={!editable || Boolean(busy)} onClick={() => changeOtherCosts([...referenceData.airport_other_costs, { airport: '', amount: 0 }])}>Add cost</button></div></div>
      {!editable && <div className="admin-empty">Создайте draft, чтобы изменить Reference Data.</div>}
      <div className="admin-table-wrap reference-table-wrap"><table className="admin-table reference-data-table"><thead><tr><th>Airport</th><th>Amount</th><th>Action</th></tr></thead><tbody>{visibleOtherCosts.map(({ item, index }) => <tr key={`${item.airport}-${index}`}><td><input aria-label={`Other cost ${index + 1} airport`} value={item.airport} disabled={!editable || Boolean(busy)} onChange={(event) => updateOtherCost(index, { airport: event.target.value.toUpperCase() })} /></td><td><input aria-label={`Other cost ${index + 1} amount`} type="number" min="0" step="0.01" value={item.amount} disabled={!editable || Boolean(busy)} onChange={(event) => updateOtherCost(index, { amount: Number(event.target.value) })} /></td><td><button disabled={!editable || Boolean(busy)} onClick={() => changeOtherCosts(referenceData.airport_other_costs.filter((_, itemIndex) => itemIndex !== index))}>Delete</button></td></tr>)}</tbody></table></div>
      {visibleOtherCosts.length === 0 && <div className="admin-empty">Airport Other Costs не найдены.</div>}
    </section>

    <section className="admin-card"><div className="section-heading"><div><h2>Reference versions, Compare и Rollback</h2><p>Сравнение active/inactive/draft snapshots и immutable version history.</p></div></div>
      <div className="admin-compare-controls"><select value={leftVersion ?? ''} onChange={(event) => setLeftVersion(Number(event.target.value))}>{selectableVersions.map((version) => <option key={version} value={version}>v{version}{draft?.version === version ? ' (draft)' : ''}</option>)}</select><span>→</span><select value={rightVersion ?? ''} onChange={(event) => setRightVersion(Number(event.target.value))}>{selectableVersions.map((version) => <option key={version} value={version}>v{version}{draft?.version === version ? ' (draft)' : ''}</option>)}</select><button className="button button-secondary" disabled={leftVersion === null || rightVersion === null || leftVersion === rightVersion || Boolean(busy)} onClick={() => leftVersion !== null && rightVersion !== null && props.onCompare(leftVersion, rightVersion)}>Compare</button></div>
      <div className="admin-table-wrap"><table className="admin-table"><thead><tr><th>Version</th><th>State</th><th>Created</th><th>Action</th></tr></thead><tbody>{orderedVersions.map((version) => <tr key={version.version}><td>v{version.version}</td><td><span className={`admin-state ${version.state}`}>{version.state}</span></td><td>{dateTime(version.created_at)}</td><td><button disabled={version.state === 'active' || Boolean(busy)} onClick={() => props.onRollback(version.version)}>Rollback</button></td></tr>)}</tbody></table></div>
      {comparison && (comparison.changes.length ? <div className="admin-table-wrap reference-comparison-table"><table className="admin-table"><thead><tr><th>Change</th><th>Path</th><th>Before</th><th>After</th></tr></thead><tbody>{comparison.changes.map((change, index) => <tr key={`${change.path}-${index}`}><td><b>{change.summary}</b><small>{change.kind}</small></td><td><code>{change.path}</code></td><td><pre>{valueText(change.before)}</pre></td><td><pre>{valueText(change.after)}</pre></td></tr>)}</tbody></table></div> : <div className="admin-empty">Версии Reference Data совпадают.</div>)}
    </section>

    <section className="admin-card"><div className="section-heading"><div><h2>Reference preview</h2><p>Active Configuration и live dataset остаются неизменными; меняется только draft Reference Data.</p></div></div>
      {!preview ? <div className="admin-empty">Создайте draft и выполните Preview для control route.</div> : <div className="preview-comparison"><article><span>Active Reference v{preview.active.reference_version}</span><b>M2 {number.format(preview.active.total.m2)}</b></article><article><span>Draft Reference v{preview.draft.reference_version}</span><b>M2 {number.format(preview.draft.total.m2)}</b></article><article><span>Difference</span><b>{number.format(preview.difference.total.m2)}</b></article></div>}
    </section>
  </>
}
