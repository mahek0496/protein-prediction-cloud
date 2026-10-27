import { StatusBadge, fmtSec } from './common.jsx'

function Node({ t, small }) {
  if (!t) return null
  return (
    <div className={`node node-${t.status} ${t.group === 'parallel' ? 'node-parallel' : ''} ${small ? 'node-small' : ''}`}
      title={t.error || t.summary || t.description}>
      <div className="node-head">
        <span className="node-id">{t.id === 'UPLOAD' ? 'S3' : t.id}</span>
        <StatusBadge status={t.status} />
      </div>
      <div className="node-name">{t.name}</div>
      <div className="node-time">{fmtSec(t.duration_seconds)}</div>
      {t.error && <div className="node-error">{t.error}</div>}
    </div>
  )
}

const Arrow = () => <div className="arrow" aria-hidden>↓</div>

/** Dependency graph: A → B → [C..H in parallel] → I → storage upload. */
export default function WorkflowGraph({ tasks }) {
  const by = Object.fromEntries((tasks || []).map((t) => [t.id, t]))
  const parallel = ['C', 'D', 'E', 'F', 'G', 'H'].map((id) => by[id])
  return (
    <div className="graph">
      <Node t={by.A} />
      <Arrow />
      <Node t={by.B} />
      <Arrow />
      <div className="parallel-box">
        <div className="parallel-label">Tasks C–H · independent · run concurrently (ThreadPoolExecutor)</div>
        <div className="parallel-grid">{parallel.map((t) => <Node key={t?.id} t={t} small />)}</div>
      </div>
      <Arrow />
      <Node t={by.I} />
      <Arrow />
      <Node t={by.UPLOAD} />
    </div>
  )
}
