import { useEffect, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { Bar, BarChart, CartesianGrid, Legend, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import { api } from '../services/api.js'
import { EXAMPLES } from '../services/examples.js'
import TaskTimeline from '../components/TaskTimeline.jsx'
import { ErrorBox, fmtSec } from '../components/common.jsx'

const Stat = ({ label, value }) => <div className="stat"><span>{label}</span><b>{value}</b></div>

function JobMetrics({ jobId }) {
  const [data, setData] = useState(null)
  const [error, setError] = useState(null)
  useEffect(() => { api.results(jobId).then(setData).catch((e) => setError(e.message)) }, [jobId])
  if (error) return <ErrorBox error={error} />
  if (!data) return <p className="muted">Loading…</p>
  const m = data.metrics
  if (!m) return <p className="muted">Metrics appear when the job finishes. <Link to={`/workflow/${jobId}`}>Open workflow</Link></p>
  const chart = data.tasks.map((t) => ({ task: t.id === 'UPLOAD' ? 'S3' : t.id, seconds: t.duration_seconds ?? 0 }))
  return (
    <>
      <div className="stats">
        <Stat label="Mode" value={`${m.execution_mode} (${m.workers} worker${m.workers > 1 ? 's' : ''})`} />
        <Stat label="Total elapsed" value={fmtSec(m.total_wall_seconds)} />
        <Stat label="C–H stage elapsed" value={fmtSec(m.parallel_stage_wall_seconds)} />
        <Stat label="Sum of C–H durations" value={fmtSec(m.parallel_stage_sum_seconds)} />
        <Stat label="Overlap factor (sum ÷ elapsed)" value={m.speedup_vs_sum ? `${m.speedup_vs_sum}×` : '–'} />
        <Stat label="Artificial delay" value={m.artificial_delay_seconds ? `${m.artificial_delay_seconds}s per task C–G` : 'none'} />
      </div>
      <ResponsiveContainer width="100%" height={240}>
        <BarChart data={chart}>
          <CartesianGrid strokeDasharray="3 3" stroke="#e5e7eb" />
          <XAxis dataKey="task" />
          <YAxis unit="s" />
          <Tooltip formatter={(v) => fmtSec(v)} />
          <Bar dataKey="seconds" fill="#1d4ed8" name="Task duration" isAnimationActive={false} />
        </BarChart>
      </ResponsiveContainer>
      <TaskTimeline tasks={data.tasks} />
    </>
  )
}

function Benchmark() {
  const [delay, setDelay] = useState(1)
  const [result, setResult] = useState(null)
  const [running, setRunning] = useState(false)
  const [error, setError] = useState(null)
  async function run() {
    setRunning(true); setError(null)
    try { setResult(await api.benchmark({ sequence: EXAMPLES[0].value, demo_delay_seconds: Number(delay) })) }
    catch (e) { setError(e.message) }
    setRunning(false)
  }
  const chart = result && result.tasks_benchmarked.map((t) => ({
    task: t,
    sequential_end: result.runs.sequential.tasks[t].end_offset,
    parallel_end: result.runs.parallel.tasks[t].end_offset,
  }))
  return (
    <>
      <p className="small">Runs tasks C–G on the ubiquitin example twice on the server: once with 1 worker (sequential),
        once with 5 workers (parallel). Task H is excluded so the external ESMFold API is not called twice.</p>
      <div className="row">
        <label className="inline">Artificial delay per task:
          <select value={delay} onChange={(e) => setDelay(e.target.value)}>
            <option value={0}>0 s (real compute only)</option><option value={0.5}>0.5 s</option>
            <option value={1}>1 s</option><option value={2}>2 s</option>
          </select>
        </label>
        <button className="btn" onClick={run} disabled={running}>{running ? 'Running…' : 'Run benchmark'}</button>
      </div>
      <ErrorBox error={error} />
      {result && (
        <>
          <div className="stats">
            <Stat label="Sequential elapsed" value={fmtSec(result.runs.sequential.wall_seconds)} />
            <Stat label="Parallel elapsed" value={fmtSec(result.runs.parallel.wall_seconds)} />
            <Stat label="Speed-up" value={result.speedup ? `${result.speedup}×` : '–'} />
          </div>
          <ResponsiveContainer width="100%" height={240}>
            <BarChart data={[{ mode: 'Sequential', seconds: result.runs.sequential.wall_seconds }, { mode: 'Parallel', seconds: result.runs.parallel.wall_seconds }]}>
              <CartesianGrid strokeDasharray="3 3" stroke="#e5e7eb" />
              <XAxis dataKey="mode" /><YAxis unit="s" /><Tooltip formatter={(v) => fmtSec(v)} />
              <Bar dataKey="seconds" fill="#0f766e" name="Elapsed time" isAnimationActive={false} />
            </BarChart>
          </ResponsiveContainer>
          <h3>When each task finished</h3>
          <ResponsiveContainer width="100%" height={220}>
            <BarChart data={chart}>
              <CartesianGrid strokeDasharray="3 3" stroke="#e5e7eb" />
              <XAxis dataKey="task" /><YAxis unit="s" /><Tooltip formatter={(v) => fmtSec(v)} /><Legend />
              <Bar dataKey="sequential_end" fill="#93c5fd" name="Sequential" isAnimationActive={false} />
              <Bar dataKey="parallel_end" fill="#0f766e" name="Parallel" isAnimationActive={false} />
            </BarChart>
          </ResponsiveContainer>
          <p className="muted small">{result.note}</p>
        </>
      )}
    </>
  )
}

export default function PerformancePage({ fallbackId }) {
  const jobId = useParams().jobId || fallbackId
  return (
    <>
      <header className="page-head">
        <h1>Execution performance</h1>
        <p>Sequential vs parallel execution of the independent analysis tasks.</p>
      </header>
      <div className="grid-2">
        <section className="card">
          <h2>Selected job</h2>
          {jobId ? <JobMetrics jobId={jobId} /> : <p className="muted">No job selected yet.</p>}
        </section>
        <section className="card">
          <h2>Sequential vs parallel benchmark</h2>
          <Benchmark />
        </section>
      </div>
      <section className="card">
        <h2>Why parallel execution is faster</h2>
        <p>After Task B, tasks C–H only need the sequence and feature vector, and none needs another's output. The scheduler
          submits all six to a <code>ThreadPoolExecutor</code> at once, so the stage takes roughly as long as the
          <i> slowest</i> task instead of the <i>sum</i> of all tasks. Task I starts only after every C–H task has finished.</p>
        <p>Threads give a real speed-up when tasks wait on I/O, such as the ESMFold network call (Task H) or the artificial
          sleep. The local analyses (C–G) finish in milliseconds and are limited by Python's GIL, so with no delay the
          difference is tiny or even negative because of thread overhead. A <code>ProcessPoolExecutor</code> or more EC2
          instances would be the next step for heavy CPU work.</p>
        <p className="small muted">Speed-up = sequential time ÷ parallel time. Ideal speed-up for 5 equal tasks is 5×.</p>
      </section>
    </>
  )
}
