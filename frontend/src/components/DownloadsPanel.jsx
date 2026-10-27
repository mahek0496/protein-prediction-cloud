import { useEffect, useState } from 'react'
import { absoluteUrl, api } from '../services/api.js'
import { ErrorBox } from './common.jsx'

/** Lists stored files. For S3 the backend returns time-limited presigned URLs (fetched on demand). */
export default function DownloadsPanel({ jobId, storageErrors }) {
  const [files, setFiles] = useState(null)
  const [error, setError] = useState(null)
  const [fetchedAt, setFetchedAt] = useState(null)

  const load = () => api.downloads(jobId)
    .then((d) => { setFiles(d.files); setFetchedAt(Date.now()); setError(null) })
    .catch((e) => setError(e.message))
  useEffect(() => { load() }, [jobId])

  return (
    <div>
      {(storageErrors || []).map((e) => <div key={e} className="state state-warn">{e}</div>)}
      <ErrorBox error={error} />
      {files && !files.length && <p className="muted">No stored files for this job.</p>}
      {files && files.length > 0 && (
        <table className="table">
          <thead><tr><th>File</th><th>Stored in</th><th>Size</th><th>Link</th></tr></thead>
          <tbody>
            {files.map((f) => (
              <tr key={f.filename}>
                <td><code>{f.filename}</code></td>
                <td><span className={`tag ${f.backend === 's3' ? 'tag-s3' : 'tag-local'}`}>{f.backend === 's3' ? 'Amazon S3' : 'Server disk'}</span></td>
                <td>{f.size_bytes != null ? `${(f.size_bytes / 1024).toFixed(1)} KB` : '–'}</td>
                <td>
                  {f.error ? <span className="error-text">{f.error}</span> : (
                    <a className="btn btn-small" href={absoluteUrl(f.url)} download>Download</a>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
      {files?.some((f) => f.backend === 's3') && (
        <p className="muted small">
          S3 links are presigned URLs valid for {Math.round((files.find((f) => f.expires_in)?.expires_in || 0) / 60)} minutes
          (generated {fetchedAt ? new Date(fetchedAt).toLocaleTimeString() : ''}). <button className="link" onClick={load}>Refresh links</button>
        </p>
      )}
    </div>
  )
}
