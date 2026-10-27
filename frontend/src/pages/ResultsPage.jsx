import { useEffect, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { Bar, BarChart, CartesianGrid, Line, LineChart, ReferenceLine, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import { api } from '../services/api.js'
import ProteinViewer from '../components/ProteinViewer.jsx'
import DownloadsPanel from '../components/DownloadsPanel.jsx'
import { Empty, ErrorBox, Loading, StatusBadge, TypeTag, fmtSec } from '../components/common.jsx'

const BLUE = '#1d4ed8'
const TEAL = '#0f766e'

function Section({ title, type, children, note }) {
  return (
    <section className="card">
      <div className="section-head"><h2>{title}</h2><TypeTag type={type} /></div>
      {note && <p className="note">{note}</p>}
      {children}
    </section>
  )
}

const Stat = ({ label, value }) => <div className="stat"><span>{label}</span><b>{value}</b></div>

function TaskError({ r }) {
  return r?.error ? <div className="state state-error">Task {r.status}: {r.error}</div> : null
}

export default function ResultsPage({ fallbackId }) {
  const jobId = useParams().jobId || fallbackId
  const [data, setData] = useState(null)
  const [error, setError] = useState(null)
  useEffect(() => {
    if (!jobId) return
    setData(null)
    api.results(jobId).then(setData).catch((e) => setError(e.message))
  }, [jobId])

  if (!jobId) return <Empty>No job selected. <Link to="/">Submit a sequence</Link> or open one from <Link to="/history">History</Link>.</Empty>
  if (error) return <ErrorBox error={error} />
  if (!data) return <Loading text="Loading results…" />
  if (data.status === 'queued' || data.status === 'running') {
    return <Empty>This job is still {data.status}. <Link to={`/workflow/${jobId}`}>Watch the workflow</Link>.</Empty>
  }
  const r = data.report
  if (!r) return <div className="state state-error">The job failed before a report was produced: {data.error}</div>

  const A = r.sequence_analysis
  const { C, D, E, F, G } = r.analyses
  const H = r.structure
  const comp = Object.entries(A.composition_percent).map(([aa, pct]) => ({ aa, pct }))

  return (
    <>
      <header className="page-head">
        <h1>Results: {r.name}</h1>
        <p>{r.length} residues · <StatusBadge status={data.status} /> · {data.execution_mode} · total {fmtSec(data.total_seconds)} ·{' '}
          <Link to={`/performance/${jobId}`}>performance</Link></p>
      </header>

      <div className="disclosure">
        <b>How to read these results</b>
        <ul>{r.disclosures.map((d) => <li key={d}>{d}</li>)}</ul>
      </div>

      <Section title="3D structure prediction (Task H)" type={H.available ? 'ml_prediction' : undefined}>
        {H.available ? (
          <div className="grid-2">
            <ProteinViewer url={api.structureUrl(jobId)} />
            <div>
              <div className="stats">
                <Stat label="Engine" value={H.engine} />
                <Stat label="Mean pLDDT" value={H.mean_plddt} />
                <Stat label="Residues pLDDT > 70" value={(H.confidence_bands['very_high_>90'] + H.confidence_bands.confident_70_90)} />
              </div>
              <p className="note">{H.disclaimer}</p>
              <ResponsiveContainer width="100%" height={200}>
                <LineChart data={H.per_residue_plddt.map((v, i) => ({ pos: i + 1, plddt: v }))}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#e5e7eb" />
                  <XAxis dataKey="pos" tick={{ fontSize: 11 }} />
                  <YAxis domain={[0, 100]} tick={{ fontSize: 11 }} />
                  <Tooltip />
                  <ReferenceLine y={70} stroke="#9ca3af" strokeDasharray="4 4" />
                  <Line type="monotone" dataKey="plddt" stroke={BLUE} dot={false} name="pLDDT" isAnimationActive={false} />
                </LineChart>
              </ResponsiveContainer>
            </div>
          </div>
        ) : (
          <div className="state state-warn">
            <b>3D structure prediction is not available for this run.</b> {H.reason} No coordinates were generated,
            so no structure is displayed or stored.
          </div>
        )}
      </Section>

      <Section title="Stored results (Amazon S3)">
        <DownloadsPanel jobId={jobId} storageErrors={data.storage_errors} />
      </Section>

      <div className="grid-2">
        <Section title="Sequence analysis (Task A)" type="calculation">
          <div className="stats">
            <Stat label="Length" value={`${A.length} aa`} />
            <Stat label="Most common" value={A.most_common.slice(0, 3).map((m) => `${m.residue}(${m.count})`).join(' ')} />
            <Stat label="Starts with Met" value={A.starts_with_methionine ? 'Yes' : 'No'} />
          </div>
          <ResponsiveContainer width="100%" height={220}>
            <BarChart data={comp}>
              <CartesianGrid strokeDasharray="3 3" stroke="#e5e7eb" />
              <XAxis dataKey="aa" tick={{ fontSize: 11 }} interval={0} />
              <YAxis unit="%" tick={{ fontSize: 11 }} />
              <Tooltip formatter={(v) => `${v}%`} />
              <Bar dataKey="pct" fill={TEAL} name="Composition" isAnimationActive={false} />
            </BarChart>
          </ResponsiveContainer>
        </Section>

        <Section title="Physicochemical profile (Task D)" type="calculation">
          <TaskError r={D} />
          {D.molecular_weight_da && (
            <>
              <div className="stats">
                <Stat label="Molecular weight" value={`${(D.molecular_weight_da / 1000).toFixed(2)} kDa`} />
                <Stat label="Isoelectric point" value={D.isoelectric_point} />
                <Stat label="GRAVY" value={`${D.gravy} (${D.hydropathy_class})`} />
                <Stat label="Instability index" value={`${D.instability_index} (${D.stability_class})`} />
                <Stat label="Aromaticity" value={D.aromaticity} />
                <Stat label="Ext. coeff. (reduced)" value={D.extinction_coefficient_reduced_cys} />
              </div>
              <p className="muted small">{D.method}</p>
            </>
          )}
        </Section>
      </div>

      <Section title="Secondary-structure propensity (Task C)" type="empirical_estimate" note={C.disclaimer}>
        <TaskError r={C} />
        {C.per_residue_states && (
          <>
            <div className="ss-seq">
              {r.sequence.split('').map((aa, i) => (
                <span key={i} className={`ss ss-${C.per_residue_states[i]}`} title={`${aa}${i + 1}: ${C.per_residue_states[i]}`}>{aa}</span>
              ))}
            </div>
            <p className="small">
              <span className="ss ss-H">H</span> helix-favouring {C.fractions_percent.helix}% ·{' '}
              <span className="ss ss-E">E</span> strand-favouring {C.fractions_percent.strand}% ·{' '}
              <span className="ss ss-C">C</span> coil {C.fractions_percent.coil}%
            </p>
          </>
        )}
      </Section>

      <div className="grid-2">
        <Section title="Hydropathy & transmembrane screen (Task E)" type="rule_based_screen" note={E.disclaimer}>
          <TaskError r={E} />
          {E.profile && (
            <>
              <ResponsiveContainer width="100%" height={220}>
                <LineChart data={E.profile}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#e5e7eb" />
                  <XAxis dataKey="position" tick={{ fontSize: 11 }} />
                  <YAxis tick={{ fontSize: 11 }} />
                  <Tooltip />
                  <ReferenceLine y={0} stroke="#9ca3af" />
                  <Line type="monotone" dataKey="score" stroke={TEAL} dot={false} name="Kyte-Doolittle" isAnimationActive={false} />
                </LineChart>
              </ResponsiveContainer>
              <p className="small">{E.summary} {E.candidate_transmembrane_segments.map((s) => `${s.start}-${s.end}`).join(', ')}</p>
            </>
          )}
        </Section>

        <Section title="Charge profile (Task F)" type="calculation">
          <TaskError r={F} />
          {F.charge_curve && (
            <>
              <ResponsiveContainer width="100%" height={220}>
                <LineChart data={F.charge_curve}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#e5e7eb" />
                  <XAxis dataKey="pH" tick={{ fontSize: 11 }} />
                  <YAxis tick={{ fontSize: 11 }} />
                  <Tooltip />
                  <ReferenceLine y={0} stroke="#9ca3af" />
                  <ReferenceLine x={F.isoelectric_point} stroke={BLUE} strokeDasharray="4 4" />
                  <Line type="monotone" dataKey="charge" stroke={BLUE} dot={false} name="Net charge" isAnimationActive={false} />
                </LineChart>
              </ResponsiveContainer>
              <p className="small">{F.summary}</p>
            </>
          )}
        </Section>
      </div>

      <div className="grid-2">
        <Section title="Motif & complexity scan (Task G)" type="rule_based_screen" note={G.disclaimer}>
          <TaskError r={G} />
          {G.summary && (
            <div className="stats">
              <Stat label="N-glycosylation sites" value={G.n_glycosylation_sites.map((s) => `${s.motif}@${s.position}`).join(', ') || 'none'} />
              <Stat label="Cysteines" value={`${G.cysteine_count} (≤ ${G.max_possible_disulfide_bonds} disulfides)`} />
              <Stat label="Low-complexity regions" value={G.low_complexity_regions.map((s) => `${s.start}-${s.end}`).join(', ') || 'none'} />
              <Stat label="Pro / Gly" value={`${G.proline_percent}% / ${G.glycine_percent}%`} />
            </div>
          )}
        </Section>

        <Section title="Numerical feature vector (Task B)" type="calculation">
          <p className="small">{r.features.dimension} features: 20 composition fractions + 11 physicochemical values.</p>
          <div className="feature-grid">
            {r.features.feature_names.map((n, i) => (
              <div key={n}><span>{n}</span><b>{r.features.vector[i]}</b></div>
            ))}
          </div>
        </Section>
      </div>
    </>
  )
}
