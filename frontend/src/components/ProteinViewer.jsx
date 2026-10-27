import { useEffect, useRef, useState } from 'react'

/** 3Dmol.js viewer for a predicted PDB structure, coloured by pLDDT (B-factor column). */
export default function ProteinViewer({ url }) {
  const el = useRef(null)
  const [error, setError] = useState(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    let viewer
    let cancelled = false
    ;(async () => {
      try {
        const [$3Dmol, res] = await Promise.all([import('3dmol'), fetch(url)])
        if (!res.ok) throw new Error(`Could not load structure (HTTP ${res.status})`)
        const pdb = await res.text()
        if (cancelled || !el.current) return
        viewer = $3Dmol.createViewer(el.current, { backgroundColor: 'white' })
        viewer.addModel(pdb, 'pdb')
        // AlphaFold/ESMFold convention: orange <50, yellow 50-70, light blue 70-90, dark blue >90
        viewer.setStyle({}, {
          cartoon: {
            colorfunc: (atom) => (atom.b > 90 ? '#0053d6' : atom.b > 70 ? '#65cbf3' : atom.b > 50 ? '#ffdb13' : '#ff7d45'),
          },
        })
        viewer.zoomTo()
        viewer.render()
        setLoading(false)
      } catch (e) {
        if (!cancelled) { setError(e.message); setLoading(false) }
      }
    })()
    return () => { cancelled = true; viewer?.clear?.() }
  }, [url])

  return (
    <div>
      {loading && <div className="state state-loading">Loading 3D viewer…</div>}
      {error && <div className="state state-error">{error}</div>}
      <div ref={el} className="viewer" />
      <div className="legend">
        <span><i style={{ background: '#0053d6' }} />pLDDT &gt; 90</span>
        <span><i style={{ background: '#65cbf3' }} />70–90</span>
        <span><i style={{ background: '#ffdb13' }} />50–70</span>
        <span><i style={{ background: '#ff7d45' }} />&lt; 50</span>
      </div>
    </div>
  )
}
