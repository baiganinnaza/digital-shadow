import { useEffect, useState } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { api, ObjectDetail } from '../api'

export default function ObjectCard() {
  const { id } = useParams<{ id: string }>()
  const navigate = useNavigate()
  const [obj, setObj] = useState<ObjectDetail | null>(null)
  const [loading, setLoading] = useState(true)
  const [msg, setMsg] = useState('')

  useEffect(() => {
    if (!id) return
    api.object(Number(id)).then(o => { setObj(o); setLoading(false) }).catch(() => setLoading(false))
  }, [id])

  if (loading) return <p style={{ padding: 32, color: '#8b949e' }}>Загрузка...</p>
  if (!obj) return <p style={{ padding: 32, color: '#8b949e' }}>Объект не найден</p>

  const topSignal = obj.signals[0]

  async function handleCase() {
    if (!obj) return
    const title = prompt('Название дела:')
    if (!title) return
    await api.createCase(title, obj.id)
    setMsg('Дело заведено')
  }

  async function handleFalsePositive() {
    if (!topSignal) return
    await api.feedback(topSignal.id, 'false_positive')
    setMsg('Отмечено как ложное срабатывание')
  }

  return (
    <div style={{ padding: 24, maxWidth: 900 }}>
      <button onClick={() => navigate(-1)} style={btnStyle('#21262d')}>← Назад</button>

      <div style={{ margin: '16px 0 24px', display: 'flex', gap: 12, alignItems: 'center' }}>
        <h2 style={{ color: '#e6edf3' }}>{obj.key}</h2>
        <span style={{ color: '#8b949e', fontSize: 14 }}>{obj.type}</span>
      </div>

      {/* Actions */}
      <div style={{ display: 'flex', gap: 10, marginBottom: 24 }}>
        <button onClick={() => navigate(`/graph/${obj.id}`)} style={btnStyle('#1f6feb')}>
          Открыть граф
        </button>
        <button onClick={handleCase} style={btnStyle('#238636')}>
          Завести дело
        </button>
        {topSignal && (
          <button onClick={handleFalsePositive} style={btnStyle('#6e7681')}>
            Ложное срабатывание
          </button>
        )}
      </div>
      {msg && <p style={{ color: '#3d8e40', marginBottom: 16 }}>{msg}</p>}

      {/* Signals */}
      {obj.signals.length > 0 && (
        <Section title="Риск-сигналы">
          {obj.signals.map(s => (
            <div key={s.id} style={{ marginBottom: 8 }}>
              <span style={{ color: '#da3633', fontWeight: 700 }}>{(s.score * 100).toFixed(0)}%</span>
              {' '}
              <span style={{ color: '#8b949e', fontSize: 13 }}>{s.category}</span>
              {' · '}
              <span style={{ color: '#8b949e', fontSize: 12 }}>
                {(s.reasons as { rule: string; weight: number }[]).map(r => `${r.rule}(+${r.weight})`).join(', ')}
              </span>
            </div>
          ))}
        </Section>
      )}

      {/* Entities */}
      {obj.entities.length > 0 && (
        <Section title="Извлечённые сущности">
          <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 13 }}>
            <thead>
              <tr style={{ color: '#8b949e', textAlign: 'left' }}>
                <th style={th}>Тип</th><th style={th}>Значение</th><th style={th}>Conf</th>
              </tr>
            </thead>
            <tbody>
              {obj.entities.map((e, i) => (
                <tr key={i} style={{ borderBottom: '1px solid #21262d' }}>
                  <td style={td}>{e.type}</td>
                  <td style={{ ...td, fontFamily: 'monospace', color: '#79c0ff' }}>{e.value}</td>
                  <td style={td}>{e.confidence.toFixed(2)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </Section>
      )}

      {/* Provenance */}
      {obj.provenance.length > 0 && (
        <Section title="Провенанс">
          {obj.provenance.map((p, i) => (
            <div key={i} style={{ fontSize: 12, color: '#8b949e', marginBottom: 4 }}>
              {p.source} · {new Date(p.collected_at).toLocaleString('ru')}
            </div>
          ))}
        </Section>
      )}
    </div>
  )
}

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div style={{ marginBottom: 24 }}>
      <h3 style={{ color: '#8b949e', fontSize: 12, textTransform: 'uppercase', letterSpacing: 1, marginBottom: 10 }}>
        {title}
      </h3>
      <div style={{ background: '#161b22', border: '1px solid #30363d', borderRadius: 8, padding: 16 }}>
        {children}
      </div>
    </div>
  )
}

function btnStyle(bg: string): React.CSSProperties {
  return {
    background: bg, color: '#fff', border: 'none', borderRadius: 6,
    padding: '8px 16px', cursor: 'pointer', fontSize: 13,
  }
}

const th: React.CSSProperties = { padding: '4px 8px', fontWeight: 500 }
const td: React.CSSProperties = { padding: '6px 8px', color: '#e6edf3' }
