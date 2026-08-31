import { lazy, Suspense } from 'react'
import CostMonitorApp from './features/cost-monitor'

const AdminApp = lazy(() => import('./features/cost-monitor/AdminApp'))

export default function App() {
  if (window.location.pathname === '/admin' || window.location.pathname.startsWith('/admin/')) {
    return <Suspense fallback={<div className="loading-card">Загружаем административный контур…</div>}><AdminApp /></Suspense>
  }
  return <CostMonitorApp />
}
