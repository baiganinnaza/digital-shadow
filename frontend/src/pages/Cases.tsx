import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { api, CaseItem } from '../api'

export default function Cases() {
  const [cases, setCases] = useState<CaseItem[]>([])
  const [loading, setLoading] = useState(true)
  const navigate = useNavigate()

  useEffect(() => {
    api.cases().then(c => { setCases(c); setLoading(false) }).catch(() => setLoading(false))
  }, [])

  if (loading) return <p style={{ padding: 32, color: '#8b949e' }}>Загрузка...</p>

  return (
    <div style={{ padding: 24 }}>
      <h2 style={{ color: '#e6edf3', marginBottom: 16 }}>
        Дела <span style={{ color: '#8b949e', fontWeight: 400, fontSize: 14 }}>({cases.length})</span>
      </h2>

      {!cases.length && (
        <p style={{ color: '#8b949e', fontSize: 14 }}>Дел пока нет. Откройте объект и нажмите «Завести дело».</p>
      )}

      {cases.map(c => (
        <div
          key={c.id}
          onClick={() => navigate(`/objects/${c.object_id}`)}
          style={{
            background: '#161b22', border: '1px solid #30363d', borderRadius: 8,
            padding: '14px 18px', marginBottom: 10, cursor: 'pointer',
          }}
          onMouseEnter={e => (e.currentTarget.style.borderColor = '#58a6ff')}
          onMouseLeave={e => (e.currentTarget.style.borderColor = '#30363d')}
        >
          <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 4 }}>
            <span style={{ color: '#e6edf3', fontWeight: 600 }}>#{c.id} {c.title}</span>
            <span style={{ color: '#8b949e', fontSize: 12 }}>{new Date(c.created_at).toLocaleString('ru')}</span>
          </div>
          {c.note && <p style={{ color: '#8b949e', fontSize: 13 }}>{c.note}</p>}
          <p style={{ color: '#3d8e40', fontSize: 12, marginTop: 4 }}>Объект #{c.object_id}</p>
        </div>
      ))}
    </div>
  )
}
