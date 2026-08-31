import { useEffect, useMemo, useState, type ReactNode } from 'react'
import type {
  ActiveConfiguration,
  CalculationRequest,
  ConfigurationCapabilities,
  ConfigurationComparison,
  ConfigurationDraft,
  ConfigurationPreviewComparison,
  ConfigurationVersion,
  CostMonitorConfiguration,
  OperationAction,
  OperationPart,
  StepOperations,
  ValueReference,
} from '../types'

interface AdminPageProps {
  active: ActiveConfiguration | null
  versions: ConfigurationVersion[]
  capabilities: ConfigurationCapabilities | null
  draft: ConfigurationDraft | null
  configuration: CostMonitorConfiguration | null
  comparison: ConfigurationComparison | null
  preview: ConfigurationPreviewComparison | null
  calculation: CalculationRequest
  loading: boolean
  busy: string | null
  onConfigurationChange: (configuration: CostMonitorConfiguration) => void
  onCalculationChange: (calculation: CalculationRequest) => void
  onCreateDraft: () => void
  onSave: () => void
  onValidate: () => void
  onPreview: () => void
  onActivate: () => void
  onRollback: (version: number) => void
  onCompare: (left: number, right: number) => void
  referenceDataSection: ReactNode
}

const number = new Intl.NumberFormat('ru-RU', { maximumFractionDigits: 3 })
const dateTime = (value: string | null) => value ? new Date(value).toLocaleString('ru-RU') : '—'
const valueText = (value: unknown) => value === undefined ? '—' : JSON.stringify(value, null, 2)

function ReferenceEditor({ reference, capabilities, onChange, allowLookup = true }: {
  reference: ValueReference
  capabilities: ConfigurationCapabilities
  onChange: (reference: ValueReference) => void
  allowLookup?: boolean
}) {
  const kinds = allowLookup ? ['constant', 'variable', 'parameter', 'lookup'] : ['constant', 'variable', 'parameter']
  const changeKind = (kind: string) => {
    if (kind === 'variable') onChange({ kind: 'variable', name: capabilities.variables[0]?.name ?? 'distance' })
    else if (kind === 'parameter') onChange({ kind: 'parameter', path: capabilities.parameters[0] ?? 'ano.route_rate_per_100_km' })
    else if (kind === 'lookup') {
      const lookup = capabilities.lookups[0]
      const argumentsMap = Object.fromEntries((lookup?.arguments ?? []).map((argument) => [argument, { kind: 'constant' as const, value: '' }]))
      onChange({ kind: 'lookup', name: lookup?.name ?? 'airport_tariff', arguments: argumentsMap })
    } else onChange({ kind: 'constant', value: 0 })
  }
  return <div className="reference-editor">
    <select value={reference.kind} onChange={(event) => changeKind(event.target.value)}>{kinds.map((kind) => <option key={kind}>{kind}</option>)}</select>
    {reference.kind === 'constant' && <input value={Array.isArray(reference.value) ? reference.value.join(',') : String(reference.value)} onChange={(event) => {
      const raw = event.target.value
      onChange({ kind: 'constant', value: typeof reference.value === 'number' ? Number(raw) : raw })
    }} />}
    {reference.kind === 'variable' && <select value={reference.name} onChange={(event) => onChange({ kind: 'variable', name: event.target.value })}>{capabilities.variables.map((item) => <option key={item.name}>{item.name}</option>)}</select>}
    {reference.kind === 'parameter' && <select value={reference.path} onChange={(event) => onChange({ kind: 'parameter', path: event.target.value })}>{capabilities.parameters.map((path) => <option key={path}>{path}</option>)}</select>}
    {reference.kind === 'lookup' && <div className="lookup-editor">
      <select value={reference.name} onChange={(event) => {
        const lookup = capabilities.lookups.find((item) => item.name === event.target.value)
        onChange({ kind: 'lookup', name: event.target.value, arguments: Object.fromEntries((lookup?.arguments ?? []).map((argument) => [argument, { kind: 'constant' as const, value: '' }])) })
      }}>{capabilities.lookups.map((item) => <option key={item.name}>{item.name}</option>)}</select>
      {Object.entries(reference.arguments).map(([name, argument]) => <label key={name}><span>{name}</span><ReferenceEditor reference={argument} capabilities={capabilities} allowLookup={false} onChange={(next) => onChange({ ...reference, arguments: { ...reference.arguments, [name]: next as Exclude<ValueReference, { kind: 'lookup' }> } })} /></label>)}
    </div>}
  </div>
}

function OperationsEditor({ title, step, capabilities, onChange }: {
  title: string
  step: StepOperations
  capabilities: ConfigurationCapabilities
  onChange: (step: StepOperations) => void
}) {
  const updatePart = (index: number, part: OperationPart) => onChange({ ...step, parts: step.parts.map((item, itemIndex) => itemIndex === index ? part : item) })
  const move = (index: number, direction: number) => {
    const next = [...step.parts]
    const target = index + direction
    if (target < 0 || target >= next.length) return
    ;[next[index], next[target]] = [next[target], next[index]]
    onChange({ ...step, parts: next })
  }
  const addPart = () => onChange({
    ...step,
    parts: [...step.parts, {
      id: `custom_${Date.now()}`,
      label: 'Новая часть',
      detail_service: 'НАСТРАИВАЕМАЯ ЧАСТЬ',
      initial: { kind: 'constant', value: 0 },
      operations: [{ operation: 'multiply', operand: { kind: 'constant', value: 1 }, digits: null }],
      condition: null,
    }],
  })
  return <section className="admin-card operation-editor">
    <div className="section-heading"><div><h2>{title}</h2><p>Упорядоченные безопасные parts, aggregation: SUM.</p></div><button className="button button-secondary" onClick={addPart}>Добавить часть</button></div>
    {step.parts.map((part, index) => <article className="operation-part" key={part.id}>
      <div className="operation-part-heading"><b>{index + 1}. {part.label}</b><div><button onClick={() => move(index, -1)}>↑</button><button onClick={() => move(index, 1)}>↓</button><button disabled={step.parts.length === 1} onClick={() => onChange({ ...step, parts: step.parts.filter((_, itemIndex) => itemIndex !== index) })}>Удалить</button></div></div>
      <div className="admin-form-grid">
        <label><span>ID</span><input value={part.id} onChange={(event) => updatePart(index, { ...part, id: event.target.value })} /></label>
        <label><span>Название</span><input value={part.label} onChange={(event) => updatePart(index, { ...part, label: event.target.value })} /></label>
        <label><span>Detail service</span><input value={part.detail_service} onChange={(event) => updatePart(index, { ...part, detail_service: event.target.value })} /></label>
      </div>
      <label className="reference-row"><span>Initial</span><ReferenceEditor reference={part.initial} capabilities={capabilities} onChange={(initial) => updatePart(index, { ...part, initial })} /></label>
      {part.operations.map((action, actionIndex) => <div className="action-row" key={actionIndex}>
        <select value={action.operation} onChange={(event) => {
          const operation = event.target.value as OperationAction['operation']
          const next: OperationAction = operation === 'round' ? { operation, operand: null, digits: 2 } : { operation, operand: action.operand ?? { kind: 'constant', value: 1 }, digits: null }
          updatePart(index, { ...part, operations: part.operations.map((item, i) => i === actionIndex ? next : item) })
        }}>{['add', 'subtract', 'multiply', 'divide', 'round'].map((operation) => <option key={operation}>{operation}</option>)}</select>
        {action.operation === 'round' ? <input type="number" min="0" max="8" value={action.digits ?? 2} onChange={(event) => updatePart(index, { ...part, operations: part.operations.map((item, i) => i === actionIndex ? { ...item, digits: Number(event.target.value) } : item) })} /> : action.operand && <ReferenceEditor reference={action.operand} capabilities={capabilities} onChange={(operand) => updatePart(index, { ...part, operations: part.operations.map((item, i) => i === actionIndex ? { ...item, operand } : item) })} />}
        <button onClick={() => updatePart(index, { ...part, operations: part.operations.filter((_, i) => i !== actionIndex) })}>×</button>
      </div>)}
      <button className="button button-secondary" onClick={() => updatePart(index, { ...part, operations: [...part.operations, { operation: 'multiply', operand: { kind: 'constant', value: 1 }, digits: null }] })}>Добавить operation</button>
      {part.condition && <small>Condition: {part.condition.any_of.length} OR-групп, редактируется только через typed payload.</small>}
    </article>)}
  </section>
}

function JsonEditor({ value, onChange }: { value: unknown; onChange: (value: Record<string, Record<string, [number, number, number]>>) => void }) {
  const serialized = useMemo(() => JSON.stringify(value, null, 2), [value])
  const [text, setText] = useState(serialized)
  useEffect(() => setText(serialized), [serialized])
  return <textarea className="json-editor" value={text} onChange={(event) => setText(event.target.value)} onBlur={() => {
    try { onChange(JSON.parse(text) as Record<string, Record<string, [number, number, number]>>) } catch { setText(serialized) }
  }} />
}

export function AdminPage(props: AdminPageProps) {
  const { active, versions, capabilities, draft, configuration, comparison, preview, calculation, loading, busy, referenceDataSection } = props
  const [leftVersion, setLeftVersion] = useState<number | null>(null)
  const [rightVersion, setRightVersion] = useState<number | null>(null)
  const orderedVersions = [...versions].sort((a, b) => b.version - a.version)
  useEffect(() => {
    if (orderedVersions.length) {
      setLeftVersion((current) => current ?? orderedVersions[1]?.version ?? orderedVersions[0].version)
      setRightVersion((current) => current ?? orderedVersions[0].version)
    }
  }, [versions.length])
  if (loading) return <div className="loading-card">Загружаем административный контур…</div>
  if (!active || !capabilities) return <div className="information-card"><b>Configuration недоступна</b></div>

  const updateConfiguration = (mutate: (next: CostMonitorConfiguration) => void) => {
    if (!configuration) return
    const next = structuredClone(configuration)
    mutate(next)
    props.onConfigurationChange(next)
  }
  const setNumber = (group: 'fuel' | 'ano' | 'catering' | 'vat' | 'ground', key: string, value: number) => updateConfiguration((next) => {
    const target = next[group] as unknown as Record<string, unknown>
    target[key] = value
  })
  const firstLeg = calculation.legs[0]
  const setLeg = (key: keyof typeof firstLeg, value: string | number) => props.onCalculationChange({ ...calculation, legs: [{ ...firstLeg, [key]: value }] })

  return <main className="admin-main">
    <header className="admin-route-header"><div><p className="eyebrow">Отдельный административный контур</p><h1>Конфигурация Cost Monitor</h1><p>/admin · local MVP, без authentication/RBAC</p></div><a className="button button-secondary" href="/">Открыть пользовательский монитор</a></header>
    <section className="admin-summary-grid">
      <article className="admin-summary-card"><span>Активная версия</span><b>v{active.version}</b><small>schema {active.configuration.schema_version}</small></article>
      <article className="admin-summary-card"><span>Draft</span><b>{draft ? `v${draft.version}` : '—'}</b><small>{draft ? draft.validation_status : 'не создан'}</small></article>
      <article className="admin-summary-card"><span>Operation parts</span><b>{Object.values((configuration ?? active.configuration).operations).reduce((sum, step) => sum + step.parts.length, 0)}</b><small>ANO / Catering / VAT</small></article>
      <article className="admin-summary-card"><span>Capabilities</span><b>{capabilities.variables.length}</b><small>registered variables</small></article>
    </section>

    <section className="admin-toolbar admin-card"><div><b>Lifecycle</b><p>Active version immutable; изменения выполняются только через draft.</p></div><div className="admin-actions">
      <button className="button" disabled={Boolean(draft) || Boolean(busy)} onClick={props.onCreateDraft}>Create Draft</button>
      <button className="button button-secondary" disabled={!draft || Boolean(busy)} onClick={props.onSave}>Save</button>
      <button className="button button-secondary" disabled={!draft || Boolean(busy)} onClick={props.onValidate}>Validate</button>
      <button className="button button-secondary" disabled={!draft || Boolean(busy)} onClick={props.onPreview}>Preview</button>
      <button className="button" disabled={!draft || Boolean(busy)} onClick={props.onActivate}>Activate</button>
    </div></section>

    {configuration && <>
      <section className="admin-card"><div className="section-heading"><div><h2>Parameters</h2><p>Validated numeric values active only after activation.</p></div><span className="admin-version-chip">draft v{draft?.version}</span></div>
        <div className="admin-form-grid parameter-grid">
          <label><span>Fuel, т/ч</span><input type="number" value={configuration.fuel.consumption_tons_per_hour} onChange={(event) => setNumber('fuel', 'consumption_tons_per_hour', Number(event.target.value))} /></label>
          <label><span>ANO, ₽ / 100 км</span><input type="number" value={configuration.ano.route_rate_per_100_km} onChange={(event) => setNumber('ano', 'route_rate_per_100_km', Number(event.target.value))} /></label>
          <label><span>Catering units</span><input type="number" value={configuration.catering.base_units} onChange={(event) => setNumber('catering', 'base_units', Number(event.target.value))} /></label>
          <label><span>Catering base rate</span><input type="number" value={configuration.catering.base_unit_rate} onChange={(event) => setNumber('catering', 'base_unit_rate', Number(event.target.value))} /></label>
          <label><span>Passenger surcharge</span><input type="number" value={configuration.catering.passenger_surcharge} onChange={(event) => setNumber('catering', 'passenger_surcharge', Number(event.target.value))} /></label>
          <label><span>VAT</span><input type="number" step="0.01" value={configuration.vat.rate} onChange={(event) => setNumber('vat', 'rate', Number(event.target.value))} /></label>
          <label><span>Ground divisor</span><input type="number" value={configuration.ground.split_divisor} onChange={(event) => setNumber('ground', 'split_divisor', Number(event.target.value))} /></label>
          <label><span>Fire truck</span><input type="number" value={configuration.ground.fire_truck_rate} onChange={(event) => setNumber('ground', 'fire_truck_rate', Number(event.target.value))} /></label>
        </div>
      </section>
      <OperationsEditor title="ANO operations" step={configuration.operations.ano} capabilities={capabilities} onChange={(step) => updateConfiguration((next) => { next.operations.ano = step })} />
      <OperationsEditor title="Catering operations" step={configuration.operations.catering} capabilities={capabilities} onChange={(step) => updateConfiguration((next) => { next.operations.catering = step })} />
      <OperationsEditor title="VAT operations" step={configuration.operations.vat} capabilities={capabilities} onChange={(step) => updateConfiguration((next) => { next.operations.vat = step })} />
      <section className="admin-card"><div className="section-heading"><div><h2>Source-derived overrides</h2><p>Пустое значение означает использование source data.</p></div></div>
        <div className="admin-grid-two"><article><h3>Aircraft multipliers</h3>{Object.entries(configuration.overrides.aircraft_multipliers).map(([aircraft, multiplier]) => <div className="override-row" key={aircraft}><input value={aircraft} readOnly /><input type="number" value={multiplier} onChange={(event) => updateConfiguration((next) => { next.overrides.aircraft_multipliers[aircraft] = Number(event.target.value) })} /><button onClick={() => updateConfiguration((next) => { delete next.overrides.aircraft_multipliers[aircraft] })}>×</button></div>)}<button className="button button-secondary" onClick={() => updateConfiguration((next) => { next.overrides.aircraft_multipliers.NEW = 1 })}>Добавить override</button></article>
          <article><h3>Scenario rates JSON</h3><JsonEditor value={configuration.overrides.scenario_rates} onChange={(value) => updateConfiguration((next) => { next.overrides.scenario_rates = value })} /></article></div>
      </section>
    </>}

    {referenceDataSection}

    <section className="admin-card"><div className="section-heading"><div><h2>Контрольный input и Preview</h2><p>Active и draft рассчитываются на одном input, active pointer не меняется.</p></div></div>
      <div className="admin-form-grid"><label><span>DEP</span><input value={firstLeg.departure} onChange={(event) => setLeg('departure', event.target.value.toUpperCase())} /></label><label><span>ARR</span><input value={firstLeg.arrival} onChange={(event) => setLeg('arrival', event.target.value.toUpperCase())} /></label><label><span>Aircraft</span><input value={firstLeg.aircraft} onChange={(event) => setLeg('aircraft', event.target.value.toUpperCase())} /></label><label><span>Passengers</span><input type="number" value={firstLeg.passengers} onChange={(event) => setLeg('passengers', Number(event.target.value))} /></label><label><span>Scenario</span><input value={calculation.settings.scenario} onChange={(event) => props.onCalculationChange({ ...calculation, settings: { ...calculation.settings, scenario: event.target.value } })} /></label><label className="checkbox-field"><input type="checkbox" checked={calculation.settings.catering} onChange={(event) => props.onCalculationChange({ ...calculation, settings: { ...calculation.settings, catering: event.target.checked } })} /><span>Пассажирское питание</span></label></div>
      {preview && <div className="preview-comparison"><article><span>Active v{preview.active.config_version}</span><b>M2 {number.format(preview.active.total.m2)}</b></article><article><span>Draft v{preview.draft.config_version}</span><b>M2 {number.format(preview.draft.total.m2)}</b></article><article><span>Difference</span><b>{number.format(preview.difference.total.m2)}</b></article></div>}
    </section>

    <section className="admin-card"><div className="section-heading"><div><h2>Versions, Compare и Rollback</h2><p>Immutable history и semantic operation diff.</p></div></div>
      <div className="admin-compare-controls"><select value={leftVersion ?? ''} onChange={(event) => setLeftVersion(Number(event.target.value))}>{orderedVersions.map((version) => <option key={version.version} value={version.version}>v{version.version}</option>)}</select><span>→</span><select value={rightVersion ?? ''} onChange={(event) => setRightVersion(Number(event.target.value))}>{orderedVersions.map((version) => <option key={version.version} value={version.version}>v{version.version}</option>)}</select><button className="button button-secondary" disabled={leftVersion === null || rightVersion === null || leftVersion === rightVersion || Boolean(busy)} onClick={() => leftVersion !== null && rightVersion !== null && props.onCompare(leftVersion, rightVersion)}>Compare</button></div>
      <div className="admin-table-wrap"><table className="admin-table"><thead><tr><th>Version</th><th>State</th><th>Created</th><th>Action</th></tr></thead><tbody>{orderedVersions.map((version) => <tr key={version.version}><td>v{version.version}</td><td>{version.state}</td><td>{dateTime(version.created_at)}</td><td><button disabled={version.state === 'active' || Boolean(busy)} onClick={() => props.onRollback(version.version)}>Rollback</button></td></tr>)}</tbody></table></div>
      {comparison && (comparison.changes.length ? <div className="admin-table-wrap"><table className="admin-table"><thead><tr><th>Change</th><th>Path</th><th>Before</th><th>After</th></tr></thead><tbody>{comparison.changes.map((change, index) => <tr key={`${change.path}-${index}`}><td><b>{change.summary}</b><small>{change.kind}</small></td><td><code>{change.path}</code></td><td><pre>{valueText(change.before)}</pre></td><td><pre>{valueText(change.after)}</pre></td></tr>)}</tbody></table></div> : <div className="admin-empty">Версии семантически совпадают.</div>)}
    </section>

    <section className="admin-card"><div className="section-heading"><div><h2>Calculation trace</h2><p>Фактически выполненные configured parts и provenance.</p></div></div>{!preview ? <div className="admin-empty">Выполните Preview.</div> : preview.draft.trace.legs.map((leg) => <details className="admin-trace-leg" key={leg.leg_id} open><summary>{leg.leg_id} · config v{preview.draft.config_version}</summary><div className="admin-trace-steps">{leg.steps.map((step, index) => <article key={`${step.component}-${index}`}><span className={`trace-stage ${step.stage}`}>{step.stage}</span><div><b>{step.component}</b>{step.operation && <small>{step.operation}</small>}</div><pre>{JSON.stringify(step.values, null, 2)}</pre></article>)}</div></details>)}</section>
  </main>
}
