import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { api, rememberJob } from '../services/api.js'
import { Empty, ErrorBox, Loading, StatusBadge, fmtSec } from '../components/common.jsx'

export default function HistoryPage() {
  const [items, setItems] = useState(null)
  const [error, setError] = useState(null)
  const [notice, setNotice] = useState(null)
  const load = () => api.history().then((d) => setItems(d.items)).catch((e) => setError(e.message))
  useEffect(() => { load() }, [])

  async function remove(job) {
    if (!window.confirm(`Delete "${job.name}" and its stored files (including S3 objects)?`)) return
    try {
      const r = await api.deleteJob(job.id)
      setNotice(r.storage_errors.length ? `Deleted with warnings: ${r.storage_errors.join('; ')}` : 'Deleted.')
      load()
    } catch (e) { setError(e.message) }
  }

  return (
    <>
      <header className="page-head"><h1>Prediction history</h1><p>Runs saved in SQLite on the server. Files live in S3 or on server disk.</p></header>
      <ErrorBox error={error} />
      {notice && <div className="state state-success">{notice}</div>}
      {items === null && !error && <Loading />}
      {items?.length === 0 && <Empty>No predictions yet. <Link to="/">Submit one</Link>.</Empty>}
      {items?.length > 0 && (
        <div className="card">
          <table className="table">
            <thead><tr><th>Name</th><th>Created</th><th>Length</th><th>Mode</th><th>Status</th><th>Time</th><th>Storage</th><th /></tr></thead>
            <tbody>
              {items.map((j) => (
                <tr key={j.id}>
                  <td><b>{j.name}</b><div className="muted small mono">{j.sequence_preview}…</div></td>
                  <td className="small">{new Date(j.created_at).toLocaleString()}</td>
                  <td>{j.length}</td>
                  <td>{j.execution_mode}</td>
                  <td><StatusBadge status={j.status} /></td>
                  <td>{fmtSec(j.total_seconds)}</td>
                  <td>{j.storage.map((s) => <span key={s} className={`tag ${s === 's3' ? 'tag-s3' : 'tag-local'}`}>{s === 's3' ? 'S3' : 'local'}</span>)}</td>
                  <td className="actions">
                    <Link className="btn btn-small" to={`/results/${j.id}`} onClick={() => rememberJob(j.id)}>Open</Link>
                    <button className="btn btn-small btn-danger" onClick={() => remove(j)} disabled={j.status === 'running' || j.status === 'queued'}>Delete</button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </>
  )
}
