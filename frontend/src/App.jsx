import { NavLink, Route, Routes } from 'react-router-dom'
import Dashboard from './pages/Dashboard.jsx'
import WorkflowPage from './pages/WorkflowPage.jsx'
import ResultsPage from './pages/ResultsPage.jsx'
import PerformancePage from './pages/PerformancePage.jsx'
import HistoryPage from './pages/HistoryPage.jsx'
import CloudPage from './pages/CloudPage.jsx'
import { lastJob } from './services/api.js'

const NAV = [
  { to: '/', label: 'Dashboard', end: true },
  { to: '/workflow', label: 'Workflow' },
  { to: '/results', label: 'Results' },
  { to: '/performance', label: 'Performance' },
  { to: '/history', label: 'History' },
  { to: '/cloud', label: 'AWS Cloud Status' },
]

export default function App() {
  return (
    <div className="layout">
      <aside className="sidebar">
        <div className="brand">
          <span className="brand-dot" />
          <div>
            <strong>ProteinCloud</strong>
            <small>Structure prediction on AWS</small>
          </div>
        </div>
        <nav>
          {NAV.map((n) => (
            <NavLink key={n.to} to={n.to} end={n.end} className={({ isActive }) => (isActive ? 'active' : '')}>
              {n.label}
            </NavLink>
          ))}
        </nav>
        <p className="sidebar-foot">React + FastAPI + EC2 + S3 + IAM</p>
      </aside>
      <main className="content">
        <Routes>
          <Route path="/" element={<Dashboard />} />
          <Route path="/workflow/:jobId?" element={<WorkflowPage fallbackId={lastJob()} />} />
          <Route path="/results/:jobId?" element={<ResultsPage fallbackId={lastJob()} />} />
          <Route path="/performance/:jobId?" element={<PerformancePage fallbackId={lastJob()} />} />
          <Route path="/history" element={<HistoryPage />} />
          <Route path="/cloud" element={<CloudPage />} />
          <Route path="*" element={<div className="card">Page not found.</div>} />
        </Routes>
      </main>
    </div>
  )
}
