import { Link, useParams } from 'react-router-dom'
import WorkflowGraph from '../components/WorkflowGraph.jsx'
import TaskTimeline from '../components/TaskTimeline.jsx'
import { Empty, ErrorBox, Loading, StatusBadge, fmtSec, useJobStatus } from '../components/common.jsx'

export default function WorkflowPage({ fallbackId }) {
  const jobId = useParams().jobId || fallbackId
  const { data, error } = useJobStatus(jobId)
  if (!jobId) return <Empty>No job selected. <Link to="/">Submit a sequence</Link> first.</Empty>
  if (!data) return error ? <ErrorBox error={error} /> : <Loading text="Loading workflow…" />
  const finished = data.status === 'completed' || data.status === 'failed'

  return (
    <>
      <header className="page-head">
        <h1>Workflow: {data.name}</h1>
        <p>Job <code>{jobId.slice(0, 8)}</code> · mode <b>{data.execution_mode}</b> · status <StatusBadge status={data.status} />
          {data.demo_delay_seconds > 0 && <> · <span className="tag tag-warn">artificial delay {data.demo_delay_seconds}s per task C–G</span></>}</p>
      </header>
      <ErrorBox error={error} />
      {data.error && <div className={data.status === 'failed' ? 'state state-error' : 'state state-warn'}>{data.error}</div>}
      <div className="progress"><div style={{ width: `${data.progress_percent}%` }} /></div>
      <p className="muted small">{data.progress_percent}% of tasks finished{data.total_seconds != null && ` · total ${fmtSec(data.total_seconds)}`}</p>

      <div className="grid-2">
        <div className="card"><h2>Task dependency graph</h2><WorkflowGraph tasks={data.tasks} /></div>
        <div className="card">
          <h2>Execution timeline</h2>
          <p className="muted small">Bars that overlap ran at the same time. In sequential mode they line up one after another.</p>
          <TaskTimeline tasks={data.tasks} />
          <h3>Task details</h3>
          <table className="table">
            <thead><tr><th>Task</th><th>Status</th><th>Duration</th><th>Result</th></tr></thead>
            <tbody>
              {data.tasks.map((t) => (
                <tr key={t.id}>
                  <td><b>{t.id === 'UPLOAD' ? 'S3' : t.id}</b> {t.name}</td>
                  <td><StatusBadge status={t.status} /></td>
                  <td>{fmtSec(t.duration_seconds)}</td>
                  <td className="small">{t.error ? <span className="error-text">{t.error}</span> : t.summary}</td>
                </tr>
              ))}
            </tbody>
          </table>
          {finished && (
            <div className="row">
              <Link className="btn" to={`/results/${jobId}`}>View results</Link>
              <Link className="btn btn-ghost" to={`/performance/${jobId}`}>Performance</Link>
            </div>
          )}
        </div>
      </div>
    </>
  )
}
