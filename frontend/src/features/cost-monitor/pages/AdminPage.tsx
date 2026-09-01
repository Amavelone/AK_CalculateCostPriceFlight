import { useEffect, useState, type ReactNode } from 'react'
import type {
  ActiveConfiguration,
  CalculationRequest,
  ConfigurationCapabilities,
  ConfigurationComparison,
  ConfigurationDraft,
  ConfigurationPreviewComparison,
  ConfigurationPresentation,
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
  presentation: ConfigurationPresentation | null
  draft: ConfigurationDraft | null
  configuration: CostMonitorConfiguration | null
  comparison: ConfigurationComparison | null
  preview: ConfigurationPreviewComparison | null
  calculation: CalculationRequest
  loading: boolean
  busy: string | null
  onConfigurationChange: (configuration: CostMonitorConfiguration) => void
  onCalculationChange: (calculation: CalculationRequest) => void
  onCreateDraft: (base: 'default' | 'active') => void
  onSave: () => void
  onValidate: () => void
  onPreview: () => void
  onActivate: () => void
  onRollback: (version: number) => void
  onCompare: (left: number, right: number) => void
  onDeleteDraft: () => void
  onExport: (version: number) => void
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

function BusinessParameter({ parameter, value, disabled, onChange }: {
  parameter: ConfigurationPresentation['parameters'][number]
  value: unknown
  disabled: boolean
  onChange: (value: unknown) => void
}) {
  const bounds = parameter.bounds
  const numberValue = typeof value === 'number'
  return <article className="business-parameter">
    <div><h3>{parameter.label}</h3><p>{parameter.description}</p></div>
    <label><span>Значение{parameter.unit ? `, ${parameter.unit}` : ''}</span>{Array.isArray(value)
      ? <input disabled={disabled} value={value.join(', ')} onChange={(event) => onChange(event.target.value.split(',').map((item) => item.trim().toUpperCase()).filter(Boolean))} />
      : <input disabled={disabled} type={numberValue ? 'number' : 'text'} min={bounds.min} max={bounds.max} step={parameter.unit === '%' ? 0.01 : 'any'} value={String(value)} onChange={(event) => onChange(numberValue ? Number(event.target.value) : event.target.value)} />}</label>
    <small><b>Где используется:</b> {parameter.where_used.join(' · ')}</small>
    <small>Допустимые границы: {bounds.exclusive_min !== undefined ? `больше ${bounds.exclusive_min}` : `от ${bounds.min ?? '—'}`} до {bounds.max ?? '—'}</small>
  </article>
}

export function AdminPage(props: AdminPageProps) {
  const { active, versions, capabilities, presentation, draft, configuration, comparison, preview, calculation, loading, busy, referenceDataSection } = props
  const [leftVersion, setLeftVersion] = useState<number | null>(null)
  const [rightVersion, setRightVersion] = useState<number | null>(null)
  const [section, setSection] = useState('overview')
  const [advanced, setAdvanced] = useState(false)
  const orderedVersions = [...versions].sort((a, b) => b.version - a.version)
  const defaultVersion = versions.find((version) => version.is_default)?.version
  const selectableVersions = draft ? [draft.version, ...orderedVersions.map((version) => version.version)] : orderedVersions.map((version) => version.version)
  useEffect(() => {
    if (selectableVersions.length) {
      setLeftVersion((current) => current ?? defaultVersion ?? selectableVersions[0])
      setRightVersion((current) => current ?? (draft?.version ?? selectableVersions[0]))
    }
  }, [defaultVersion, draft?.version, selectableVersions.length])
  if (loading) return <div className="loading-card">Загружаем административный контур…</div>
  if (!active || !capabilities || !presentation) return <div className="information-card"><b>Configuration недоступна</b></div>

  const updateConfiguration = (mutate: (next: CostMonitorConfiguration) => void) => {
    if (!configuration) return
    const next = structuredClone(configuration)
    mutate(next)
    props.onConfigurationChange(next)
  }
  const displayConfiguration = configuration ?? active.configuration
  const readValue = (path: string): unknown => path.split('.').reduce<unknown>((value, key) => (value as Record<string, unknown>)[key], displayConfiguration)
  const setBusinessValue = (path: string, value: unknown) => updateConfiguration((next) => {
    const parts = path.split('.')
    const leaf = parts.pop() as string
    const target = parts.reduce<Record<string, unknown>>((current, key) => current[key] as Record<string, unknown>, next as unknown as Record<string, unknown>)
    target[leaf] = value
  })
  const firstLeg = calculation.legs[0]
  const setLeg = (key: keyof typeof firstLeg, value: string | number) => props.onCalculationChange({ ...calculation, legs: [{ ...firstLeg, [key]: value }] })
  const editable = Boolean(draft && configuration)
  const selectedGroup = presentation.groups.find((group) => group.id === section)

  return <main className="admin-main">
    <header className="admin-route-header"><div><p className="eyebrow">Администрирование расчёта</p><h1>Calculation Configuration</h1><p>Параметры расчёта, а не внутренний execution graph.</p></div><a className="button button-secondary" href="/">Открыть пользовательский монитор</a></header>
    <section className="admin-summary-grid">
      <article className="admin-summary-card"><span>Активная версия</span><b>v{active.version}</b><small>{active.is_default ? 'DEFAULT · ACTIVE' : 'ACTIVE'}</small></article>
      <article className="admin-summary-card"><span>Эталон</span><b>v{defaultVersion ?? '—'}</b><small>DEFAULT · immutable</small></article>
      <article className="admin-summary-card"><span>Draft</span><b>{draft ? `v${draft.version}` : '—'}</b><small>{draft ? draft.validation_status : 'не создан'}</small></article>
      <article className="admin-summary-card"><span>Изменено</span><b>{comparison?.changes.length ?? 0}</b><small>сравнение с выбранной версией</small></article>
    </section>

    <section className="admin-toolbar admin-card"><div><b>Жизненный цикл</b><p>DEFAULT — постоянный эталон. Изменения возможны только в Draft.</p></div><div className="admin-actions">
      <button className="button" disabled={Boolean(draft) || Boolean(busy)} onClick={() => props.onCreateDraft('default')}>Create Draft from Default</button>
      <button className="button button-secondary" disabled={Boolean(draft) || Boolean(busy)} onClick={() => props.onCreateDraft('active')}>From Active</button>
      <button className="button button-secondary" disabled={!draft || Boolean(busy)} onClick={props.onSave}>Save</button>
      <button className="button button-secondary" disabled={!draft || Boolean(busy)} onClick={props.onValidate}>Validate</button>
      <button className="button button-secondary" disabled={!draft || Boolean(busy)} onClick={props.onPreview}>Preview</button>
      <button className="button" disabled={!draft || Boolean(busy)} onClick={props.onActivate}>Activate</button>
      <button className="button button-secondary" disabled={!draft || Boolean(busy)} onClick={props.onDeleteDraft}>Delete Draft</button>
    </div></section>

    <nav className="admin-tabs" aria-label="Разделы Configuration"><button className={section === 'overview' ? 'active' : ''} onClick={() => setSection('overview')}>Обзор</button>{presentation.groups.map((group) => <button className={section === group.id ? 'active' : ''} key={group.id} onClick={() => setSection(group.id)}>{group.label}</button>)}<button className={section === 'reference' ? 'active' : ''} onClick={() => setSection('reference')}>Справочники</button><button className={section === 'versions' ? 'active' : ''} onClick={() => setSection('versions')}>Версии / Compare</button></nav>

    {section === 'overview' && <section className="admin-card"><div className="section-heading"><div><h2>Обзор Configuration</h2><p>Сначала выберите предметный раздел. Тарифы SRV и Fuel Registry остаются в Sources, а ИШР и «Прочее» — в Reference Data.</p></div></div><div className="admin-grid-two"><article><h3>DEFAULT v{defaultVersion}</h3><p>Утверждённый immutable baseline release. Его значения нельзя редактировать, удалять или перезаписывать.</p></article><article><h3>{draft ? `Draft v${draft.version}` : `Active v${active.version}`}</h3><p>{draft ? `Основа: v${draft.base_version}. Сохраните, проверьте и активируйте только после Preview.` : 'Создайте Draft из Default или текущей Active Configuration.'}</p></article></div></section>}

    {selectedGroup && <section className="admin-card"><div className="section-heading"><div><h2>{selectedGroup.label}</h2><p>{selectedGroup.description}</p></div><span className="admin-version-chip">{editable ? `DRAFT v${draft?.version}` : active.is_default ? 'DEFAULT · ACTIVE' : `ACTIVE v${active.version}`}</span></div><div className="business-parameter-grid">{presentation.parameters.filter((parameter) => parameter.group === section).map((parameter) => <BusinessParameter key={parameter.id} parameter={parameter} value={readValue(parameter.id)} disabled={!editable || Boolean(busy)} onChange={(value) => setBusinessValue(parameter.id, value)} />)}</div></section>}

    {section === 'flight_hour' && <section className="admin-card"><div className="section-heading"><div><h2>Матрица M1 / M2 / M3</h2><p>Ставки лётного часа по сценарию и типу ВС.</p></div></div>{Object.entries(displayConfiguration.overrides.scenario_rates).map(([scenario, aircraftRates]) => <div className="admin-table-wrap" key={scenario}><h3>{scenario}</h3><table className="admin-table"><thead><tr><th>Тип ВС</th><th>M1, ₽/ч</th><th>M2, ₽/ч</th><th>M3, ₽/ч</th><th>Коэффициент НО</th></tr></thead><tbody>{Object.entries(aircraftRates).map(([aircraft, rates]) => <tr key={aircraft}><td>{aircraft}</td>{rates.map((rate, index) => <td key={index}><input disabled={!editable || Boolean(busy)} type="number" value={rate} onChange={(event) => updateConfiguration((next) => { next.overrides.scenario_rates[scenario][aircraft][index] = Number(event.target.value) })} /></td>)}<td><input disabled={!editable || Boolean(busy)} type="number" value={displayConfiguration.overrides.aircraft_multipliers[aircraft] ?? 0} onChange={(event) => updateConfiguration((next) => { next.overrides.aircraft_multipliers[aircraft] = Number(event.target.value) })} /></td></tr>)}</tbody></table></div>)}</section>}

    {section === 'reference' && referenceDataSection}

    <section className="admin-card"><div className="section-heading"><div><h2>Контрольный input и Preview</h2><p>Показывает предметное влияние Draft; active pointer не меняется.</p></div></div>
      <div className="admin-form-grid"><label><span>DEP</span><input value={firstLeg.departure} onChange={(event) => setLeg('departure', event.target.value.toUpperCase())} /></label><label><span>ARR</span><input value={firstLeg.arrival} onChange={(event) => setLeg('arrival', event.target.value.toUpperCase())} /></label><label><span>Aircraft</span><input value={firstLeg.aircraft} onChange={(event) => setLeg('aircraft', event.target.value.toUpperCase())} /></label><label><span>Passengers</span><input type="number" value={firstLeg.passengers} onChange={(event) => setLeg('passengers', Number(event.target.value))} /></label><label><span>Scenario</span><input value={calculation.settings.scenario} onChange={(event) => props.onCalculationChange({ ...calculation, settings: { ...calculation.settings, scenario: event.target.value } })} /></label><label className="checkbox-field"><input type="checkbox" checked={calculation.settings.catering} onChange={(event) => props.onCalculationChange({ ...calculation, settings: { ...calculation.settings, catering: event.target.checked } })} /><span>Пассажирское питание</span></label></div>
      {preview && <><div className="preview-comparison"><article><span>Active v{preview.active.config_version}</span><b>M2 {number.format(preview.active.total.m2)}</b></article><article><span>Draft v{preview.draft.config_version}</span><b>M2 {number.format(preview.draft.total.m2)}</b></article><article><span>Изменение</span><b>{number.format(preview.difference.total.m2)}</b></article></div><div className="admin-table-wrap"><table className="admin-table"><thead><tr><th>Плечо</th><th>Топливо</th><th>НО</th><th>АНО</th><th>Питание</th><th>НДС</th></tr></thead><tbody>{Object.entries(preview.difference.legs).map(([leg, components]) => <tr key={leg}><td>{leg}</td>{['fuel', 'ground', 'ano', 'catering', 'vat'].map((component) => <td key={component}>{number.format(components[component] ?? 0)}</td>)}</tr>)}</tbody></table></div></>}
    </section>

    {section === 'versions' && <section className="admin-card"><div className="section-heading"><div><h2>Версии, Compare и Rollback</h2><p>Сравнение открывается с DEFAULT как эталоном.</p></div></div>
      <div className="admin-compare-controls"><select value={leftVersion ?? ''} onChange={(event) => setLeftVersion(Number(event.target.value))}>{selectableVersions.map((version) => <option key={version} value={version}>v{version}{version === defaultVersion ? ' · DEFAULT' : ''}{version === draft?.version ? ' · DRAFT' : ''}</option>)}</select><span>→</span><select value={rightVersion ?? ''} onChange={(event) => setRightVersion(Number(event.target.value))}>{selectableVersions.map((version) => <option key={version} value={version}>v{version}{version === defaultVersion ? ' · DEFAULT' : ''}{version === draft?.version ? ' · DRAFT' : ''}</option>)}</select><button className="button button-secondary" disabled={leftVersion === null || rightVersion === null || leftVersion === rightVersion || Boolean(busy)} onClick={() => leftVersion !== null && rightVersion !== null && props.onCompare(leftVersion, rightVersion)}>Compare</button></div>
      <div className="admin-table-wrap"><table className="admin-table"><thead><tr><th>Version</th><th>State</th><th>Created</th><th>Actions</th></tr></thead><tbody>{orderedVersions.map((version) => <tr key={version.version}><td>v{version.version}{version.is_default && <small> DEFAULT</small>}</td><td>{version.state}{version.version === active.version && ' · ACTIVE'}</td><td>{dateTime(version.created_at)}</td><td><button disabled={version.state === 'active' || Boolean(busy)} onClick={() => props.onRollback(version.version)}>Rollback</button><button disabled={Boolean(busy)} onClick={() => props.onExport(version.version)}>Export JSON</button></td></tr>)}</tbody></table></div>
      {comparison && (comparison.changes.length ? <div className="admin-table-wrap"><table className="admin-table"><thead><tr><th>Раздел</th><th>Изменение</th><th>Было</th><th>Стало</th></tr></thead><tbody>{comparison.changes.map((change, index) => <tr key={`${change.path}-${index}`}><td>{change.presentation?.group ?? 'Advanced'}</td><td><b>{change.presentation?.label ?? change.summary}</b><small>{change.presentation?.where_used.join(' · ') ?? `Technical: ${change.path}`}</small></td><td><pre>{valueText(change.before)}</pre></td><td><pre>{valueText(change.after)}</pre></td></tr>)}</tbody></table></div> : <div className="admin-empty">Версии семантически совпадают.</div>)}
    </section>}

    <section className="admin-card"><div className="section-heading"><div><h2>Advanced</h2><p>Только для module-approved operations, conditions и lookups. Basic mode не требует этих деталей.</p></div><label className="checkbox-field"><input type="checkbox" checked={advanced} onChange={(event) => setAdvanced(event.target.checked)} /><span>Показать technical details</span></label></div>
      {advanced && configuration && <>{presentation.advanced.operations.enabled && <><OperationsEditor title="АНО: advanced composition" step={configuration.operations.ano} capabilities={capabilities} onChange={(step) => updateConfiguration((next) => { next.operations.ano = step })} /><OperationsEditor title="Бортовое питание: advanced composition" step={configuration.operations.catering} capabilities={capabilities} onChange={(step) => updateConfiguration((next) => { next.operations.catering = step })} /><OperationsEditor title="НДС: advanced composition" step={configuration.operations.vat} capabilities={capabilities} onChange={(step) => updateConfiguration((next) => { next.operations.vat = step })} /></>}<details><summary>Technical payload (read-only reference)</summary><pre>{JSON.stringify(configuration, null, 2)}</pre></details></>}
      {advanced && !configuration && <div className="admin-empty">Создайте Draft для изменения advanced composition.</div>}
    </section>

    <section className="admin-card"><div className="section-heading"><div><h2>Calculation trace</h2><p>Техническая provenance-детализация сохранена отдельно от Basic mode.</p></div></div>{!preview ? <div className="admin-empty">Выполните Preview.</div> : preview.draft.trace.legs.map((leg) => <details className="admin-trace-leg" key={leg.leg_id}><summary>{leg.leg_id} · config v{preview.draft.config_version}</summary><div className="admin-trace-steps">{leg.steps.map((step, index) => <article key={`${step.component}-${index}`}><span className={`trace-stage ${step.stage}`}>{step.stage}</span><div><b>{step.component}</b>{step.operation && <small>{step.operation}</small>}</div><pre>{JSON.stringify(step.values, null, 2)}</pre></article>)}</div></details>)}</section>
  </main>
}
