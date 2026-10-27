import { fmtSec } from './common.jsx'

/** Gantt-style timeline from task start/end offsets: overlapping bars = parallel execution. */
export default function TaskTimeline({ tasks }) {
  const rows = (tasks || []).filter((t) => t.start_offset != null)
  if (!rows.length) return <p className="muted">The timeline appears once tasks start.</p>
  const total = Math.max(...rows.map((t) => t.end_offset ?? t.start_offset), 0.001)
  return (
    <div className="timeline">
      {rows.map((t) => {
        const end = t.end_offset ?? total
        return (
          <div className="tl-row" key={t.id}>
            <span className="tl-label">{t.id === 'UPLOAD' ? 'S3' : t.id}</span>
            <div className="tl-track">
              <div className={`tl-bar tl-${t.group} tl-${t.status}`}
                style={{ left: `${(t.start_offset / total) * 100}%`, width: `${Math.max(((end - t.start_offset) / total) * 100, 0.6)}%` }}
                title={`${t.name}: ${fmtSec(t.duration_seconds)}`} />
            </div>
            <span className="tl-dur">{fmtSec(t.duration_seconds)}</span>
          </div>
        )
      })}
      <div className="tl-axis"><span>0 s</span><span>{fmtSec(total)}</span></div>
    </div>
  )
}
