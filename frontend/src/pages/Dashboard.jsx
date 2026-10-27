import { useEffect, useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { api, rememberJob } from '../services/api.js'
import { EXAMPLES } from '../services/examples.js'
import { Empty, ErrorBox, StatusBadge, fmtSec, useHealth } from '../components/common.jsx'

export default function Dashboard() {
  const nav = useNavigate()
  const { health, error: healthError } = useHealth()
  const [sequence, setSequence] = useState('')
  const [name, setName] = useState('')
  const [mode, setMode] = useState('parallel')
  const [delay, setDelay] = useState('1')
  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState(null)
  const [recent, setRecent] = useState(null)

  useEffect(() => { api.history().then((h) => setRecent(h.items.slice(0, 5))).catch(() => setRecent([])) }, [])

  const cleaned = sequence.split('\n').filter((l) => !l.startsWith('>')).join('').replace(/[\s\d*]/g, '')

  async function submit(e) {
    e.preventDefault()
    setError(null)
    if (!cleaned) { setError('Please paste a protein sequence or load an example.'); return }
    setSubmitting(true)
    try {
      const r = await api.predict({ sequence, name: name || undefined, execution_mode: mode, demo_delay_seconds: Number(delay) })
      rememberJob(r.job_id)
      nav(`/workflow/${r.job_id}`)
    } catch (err) {
      setError(err.message)
      setSubmitting(false)
    }
  }

  return (
    <>
      <header className="page-head">
        <h1>Cloud Protein Structure Prediction</h1>
        <p>Submit an amino-acid sequence. The FastAPI backend (on Amazon EC2) runs a dependency-aware workflow,
          executes six analyses in parallel, predicts a 3D structure with ESMFold when available, and stores the
          report and structure files in Amazon S3.</p>
      </header>

      <ErrorBox error={healthError} />
      {health && (
        <div className="status-strip">
          <span>Backend: <StatusBadge status={health.status === 'ok' ? 'completed' : 'failed'} label={health.status} /></span>
          <span>Storage: <b>{health.storage.backend === 's3' ? `Amazon S3 (${health.storage.bucket})` : 'Local disk (AWS not configured)'}</b>
            {!health.storage.ok && <em className="error-text"> – {health.storage.message}</em>}</span>
          <span>3D engine: <b>{health.prediction_engine.label}</b></span>
        </div>
      )}
      {health && !health.prediction_engine.genuine_prediction_available && (
        <div className="state state-warn">3D structure prediction is disabled on this server. You will get sequence analyses only;
          no structure will be shown or invented.</div>
      )}

      <div className="grid-2">
        <form className="card" onSubmit={submit}>
          <h2>Protein sequence</h2>
          <label>Sequence (FASTA or plain text, 20 standard amino acids)</label>
          <textarea rows={8} value={sequence} onChange={(e) => setSequence(e.target.value)}
            placeholder={'>my_protein\nMQIFVKTLTGKTITLEVEPSDTIENVKAKIQDKEG...'} spellCheck={false} />
          <div className="row small muted">
            <span>{cleaned.length} residues{health ? ` (allowed ${health.limits.min_length}–${health.limits.max_length})` : ''}</span>
            <span className="examples">
              {EXAMPLES.map((ex) => (
                <button type="button" key={ex.label} className="btn btn-ghost btn-small" onClick={() => setSequence(ex.value)}>{ex.label}</button>
              ))}
            </span>
          </div>
          <label>Job name (optional)</label>
          <input value={name} onChange={(e) => setName(e.target.value)} maxLength={120} placeholder="Taken from FASTA header if empty" />
          <div className="grid-2 tight">
            <div>
              <label>Execution mode</label>
              <select value={mode} onChange={(e) => setMode(e.target.value)}>
                <option value="parallel">Parallel (tasks C–H concurrently)</option>
                <option value="sequential">Sequential (one task at a time)</option>
              </select>
            </div>
            <div>
              <label>Artificial demo delay per task C–G</label>
              <select value={delay} onChange={(e) => setDelay(e.target.value)}>
                <option value="0">Off (real timings only)</option>
                <option value="1">1 second (artificial)</option>
                <option value="2">2 seconds (artificial)</option>
              </select>
            </div>
          </div>
          <p className="muted small">The demo delay is an artificial sleep that makes the parallel speed-up visible. It is
            labelled in every report. Set it to Off for real timings.</p>
          <ErrorBox error={error} />
          <button className="btn" disabled={submitting}>{submitting ? 'Submitting…' : 'Submit prediction'}</button>
        </form>

        <div className="card">
          <h2>Recent predictions</h2>
          {recent === null && <p className="muted">Loading…</p>}
          {recent?.length === 0 && <Empty>No predictions yet. Submit your first sequence.</Empty>}
          {recent?.length > 0 && (
            <table className="table">
              <thead><tr><th>Name</th><th>Status</th><th>Mode</th><th>Time</th></tr></thead>
              <tbody>
                {recent.map((j) => (
                  <tr key={j.id}>
                    <td><Link to={`/results/${j.id}`} onClick={() => rememberJob(j.id)}>{j.name}</Link></td>
                    <td><StatusBadge status={j.status} /></td>
                    <td>{j.execution_mode}</td>
                    <td>{fmtSec(j.total_seconds)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
          <h3>Workflow</h3>
          <ol className="steps">
            <li><b>A</b> Validate sequence &amp; composition</li>
            <li><b>B</b> Build numerical feature vector</li>
            <li><b>C–H</b> Six independent analyses in parallel (H = ESMFold 3D prediction)</li>
            <li><b>I</b> Combine results into a final report</li>
            <li><b>S3</b> Upload report.json, report.md, structure.pdb/.cif to Amazon S3</li>
          </ol>
        </div>
      </div>
    </>
  )
}
