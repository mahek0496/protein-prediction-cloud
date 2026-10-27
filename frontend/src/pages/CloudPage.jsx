import { API_BASE } from '../services/api.js'
import { ErrorBox, Loading, StatusBadge, useHealth } from '../components/common.jsx'

const Row = ({ k, v }) => <tr><th>{k}</th><td>{v ?? '–'}</td></tr>

export default function CloudPage() {
  const { health, error, reload } = useHealth()
  const s = health?.storage
  return (
    <>
      <header className="page-head">
        <h1>AWS cloud status</h1>
        <p>Live configuration reported by the backend. Use this page in your demo to show EC2, S3 and the IAM role at work.</p>
      </header>
      <ErrorBox error={error} />
      {!health && !error && <Loading />}
      {health && (
        <div className="grid-2">
          <section className="card">
            <h2>Compute (backend)</h2>
            <table className="kv"><tbody>
              <Row k="Backend URL used by this page" v={<code>{API_BASE || window.location.origin}</code>} />
              <Row k="Server host name" v={<code>{health.host}</code>} />
              <Row k="Environment" v={health.app_env} />
              <Row k="Overall status" v={<><StatusBadge status={health.status === 'ok' ? 'completed' : 'failed'} label={health.status} /></>} />
              <Row k="Parallel workers" v={health.limits.parallel_workers} />
              <Row k="3D prediction engine" v={health.prediction_engine.label} />
            </tbody></table>
            <p className="muted small">On EC2 the host name looks like <code>ip-172-31-…</code>.</p>
          </section>
          <section className="card">
            <h2>Storage (Amazon S3)</h2>
            <table className="kv"><tbody>
              <Row k="Backend" v={s.backend === 's3' ? 'Amazon S3' : 'Local disk (S3 not configured)'} />
              {s.backend === 's3' && <>
                <Row k="Bucket" v={<code>{s.bucket}</code>} />
                <Row k="Region" v={s.region} />
                <Row k="Key prefix" v={<code>{s.prefix}/</code>} />
                <Row k="Credential source" v={<><code>{s.credential_source || 'none found'}</code>{s.credential_source === 'iam-role' ? ' ✓ EC2 IAM role' : ''}</>} />
                <Row k="Presigned URL lifetime" v={`${health.limits.presigned_url_expiry_seconds / 60} minutes`} />
              </>}
              <Row k="Connection" v={<><StatusBadge status={s.ok ? 'completed' : 'failed'} label={s.ok ? 'connected' : 'error'} /> {s.message}</>} />
            </tbody></table>
            <p className="muted small">"iam-role" means boto3 received temporary credentials from the EC2 instance profile.
              No access keys are stored in the code, the .env file or this website.</p>
            <button className="btn btn-ghost btn-small" onClick={reload}>Re-check</button>
          </section>
        </div>
      )}
    </>
  )
}
