import { useEffect, useState } from 'react'
import { api } from '../services/api.js'

export function StatusBadge({ status, label }) {
  return <span className={`badge badge-${status || 'pending'}`}>{label || status || 'pending'}</span>
}

const TYPE_LABEL = {
  calculation: 'Calculated',
  empirical_estimate: 'Empirical estimate',
  rule_based_screen: 'Rule-based screen',
  ml_prediction: 'ML prediction (ESMFold)',
  report: 'Report',
  storage: 'Storage',
}
export function TypeTag({ type }) {
  if (!type) return null
  return <span className={`tag tag-${type}`}>{TYPE_LABEL[type] || type}</span>
}

export const Loading = ({ text = 'Loading…' }) => <div className="state state-loading">{text}</div>
export const ErrorBox = ({ error }) => (error ? <div className="state state-error">{String(error)}</div> : null)
export const Empty = ({ children }) => <div className="state state-empty">{children}</div>

export const fmtSec = (s) => (s == null ? '–' : s < 1 ? `${(s * 1000).toFixed(0)} ms` : `${s.toFixed(2)} s`)

/** Polls /api/tasks/:id every second until the job finishes. */
export function useJobStatus(jobId) {
  const [data, setData] = useState(null)
  const [error, setError] = useState(null)
  useEffect(() => {
    if (!jobId) return undefined
    let stop = false
    let timer
    const tick = async () => {
      try {
        const d = await api.tasks(jobId)
        if (stop) return
        setData(d)
        setError(null)
        if (d.status === 'queued' || d.status === 'running') timer = setTimeout(tick, 1000)
      } catch (e) {
        if (!stop) { setError(e.message); timer = setTimeout(tick, 3000) }
      }
    }
    tick()
    return () => { stop = true; clearTimeout(timer) }
  }, [jobId])
  return { data, error }
}

/** Shared backend health (storage + engine) for banners. */
export function useHealth() {
  const [health, setHealth] = useState(null)
  const [error, setError] = useState(null)
  const reload = () => api.health().then((h) => { setHealth(h); setError(null) }).catch((e) => setError(e.message))
  useEffect(() => { reload() }, [])
  return { health, error, reload }
}
