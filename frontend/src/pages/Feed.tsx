import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { api, Signal } from '../api'

const CATEGORY_COLOR: Record<string, string> = {
  vapes: '#d29922',
  alcohol: '#f78166',
  drugs: '#da3633',
  leak: '#bc8cff',
  none: '#3d444d',
}

function scoreColor(s: number) {
  if (s >= 0.75) return '#da3633'
  if (s >= 0.5) return '#d29922'
  return '#3d8e40'
}

export default function Feed() {
  const [signals, setSignals] = useState<Signal[]>([])
  const [loading, setLoading] = useState(true)
  const navigate = useNavigate()

  useEffect(() => {
    api.signals().then(s => { setSignals(s); setLoading(false) }).catch(() => setLoading(false))
  }, [])

  if (loading) return <p style={{ padding: 32, color: '#8b949e' }}>Загрузка...</p>
  if (!signals.length) return <p style={{ padding: 32, color: '#8b949e' }}>Сигналов нет. Запустите seed.py</p>

  return (
    <div style={{ padding: 24 }}>
      <h2 style={{ color: '#e6edf3', marginBottom: 16 }}>
        Сигналы риска <span style={{ color: '#8b949e', fontWeight: 400, fontSize: 14 }}>({signals.length})</span>
      </h2>
      {signals.map(sig => (
        <div
          key={sig.id}
          onClick={() => navigate(`/objects/${sig.object_id}`)}
          style={{
            background: '#161b22', border: '1px solid #30363d', borderRadius: 8,
            padding: '14px 18px', marginBottom: 10, cursor: 'pointer',
            display: 'flex', alignItems: 'center', gap: 16,
            transition: 'border-color 0.15s',
          }}
          onMouseEnter={e => (e.currentTarget.style.borderColor = '#58a6ff')}
          onMouseLeave={e => (e.currentTarget.style.borderColor = '#30363d')}
        >
          {/* Score badge */}
          <div style={{
            minWidth: 52, height: 52, borderRadius: 8,
            background: scoreColor(sig.score),
            display: 'flex', alignItems: 'center', justifyContent: 'center',
            fontWeight: 700, fontSize: 16, color: '#fff',
          }}>
            {(sig.score * 100).toFixed(0)}
          </div>

          <div style={{ flex: 1, overflow: 'hidden' }}>
            <div style={{ display: 'flex', gap: 8, alignItems: 'center', marginBottom: 6 }}>
              <span style={{
                background: CATEGORY_COLOR[sig.category] || '#3d444d',
                color: '#fff', borderRadius: 4, padding: '2px 8px', fontSize: 11, fontWeight: 600,
              }}>
                {sig.category?.toUpperCase()}
              </span>
              <span style={{ color: '#8b949e', fontSize: 12 }}>{sig.type}</span>
              <span style={{ color: '#3d8e40', fontSize: 11, marginLeft: 'auto' }}>{sig.status}</span>
            </div>
            <div style={{ color: '#e6edf3', fontSize: 13, whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
              {sig.object_key}
            </div>
            <div style={{ display: 'flex', gap: 6, marginTop: 6, flexWrap: 'wrap' }}>
              {sig.reasons.map((r, i) => (
                <span key={i} style={{
                  background: '#21262d', border: '1px solid #30363d',
                  borderRadius: 4, padding: '1px 6px', fontSize: 11, color: '#8b949e',
                }}>
                  {r.rule} +{r.weight}
                </span>
              ))}
            </div>
          </div>
        </div>
      ))}
    </div>
  )
}
