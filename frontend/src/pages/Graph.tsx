import { useEffect, useRef, useState } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import cytoscape, { Core } from 'cytoscape'
import { api, GraphData } from '../api'

function riskColor(risk: number): string {
  if (risk >= 0.75) return '#da3633'
  if (risk >= 0.5) return '#d29922'
  if (risk >= 0.25) return '#1f6feb'
  return '#3d8e40'
}

export default function GraphPage() {
  const { id } = useParams<{ id: string }>()
  const navigate = useNavigate()
  const containerRef = useRef<HTMLDivElement>(null)
  const cyRef = useRef<Core | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [tooltip, setTooltip] = useState<{ key: string; type: string; risk: number } | null>(null)

  useEffect(() => {
    if (!id || !containerRef.current) return
    setLoading(true)

    api.graph(Number(id)).then(data => {
      setLoading(false)
      initCytoscape(data)
    }).catch(e => {
      setError(String(e))
      setLoading(false)
    })

    return () => { cyRef.current?.destroy(); cyRef.current = null }
  }, [id])

  function initCytoscape(data: GraphData) {
    if (!containerRef.current) return

    const elements = [
      ...data.nodes.map(n => ({
        data: { id: n.id, label: n.key.slice(0, 20), key: n.key, type: n.type, risk: n.risk },
      })),
      ...data.edges.map((e, i) => ({
        data: { id: `e${i}`, source: e.source, target: e.target, label: e.type, reason: e.reason },
      })),
    ]

    const cy = cytoscape({
      container: containerRef.current,
      elements,
      style: [
        {
          selector: 'node',
          style: {
            'background-color': (el: any) => riskColor(el.data('risk')),
            'label': 'data(label)',
            'color': '#e6edf3',
            'font-size': 11,
            'text-valign': 'bottom',
            'text-margin-y': 4,
            width: 36,
            height: 36,
            'border-width': 2,
            'border-color': '#30363d',
          },
        },
        {
          selector: 'edge',
          style: {
            'line-color': '#30363d',
            'target-arrow-color': '#30363d',
            'target-arrow-shape': 'triangle',
            'curve-style': 'bezier',
            label: 'data(label)',
            'font-size': 9,
            color: '#8b949e',
            'text-rotation': 'autorotate',
          },
        },
        {
          selector: 'node:selected',
          style: { 'border-color': '#58a6ff', 'border-width': 3 },
        },
      ],
      layout: { name: 'cose', animate: false, randomize: false },
      userZoomingEnabled: true,
      userPanningEnabled: true,
    })

    cy.on('dblclick', 'node', async (e: any) => {
      const nodeKey = e.target.data('key')
      const nodeId = e.target.data('id')
      // Find object id from signals (use object key → navigate to graph expansion)
      // For MVP: navigate to graph of that object if we can find its DB id
      // We store object_id in node data if available, otherwise just show tooltip
      try {
        const more = await api.graph(Number(nodeId), 2)
        const existing = cy.elements().map((el: any) => el.id())
        more.nodes.forEach(n => {
          if (!cy.$id(n.id).length) {
            cy.add({ data: { id: n.id, label: n.key.slice(0, 20), key: n.key, type: n.type, risk: n.risk } })
          }
        })
        more.edges.forEach((edge, i) => {
          const eid = `e_exp_${i}_${nodeId}`
          if (!cy.$id(eid).length) {
            cy.add({ data: { id: eid, source: edge.source, target: edge.target, label: edge.type } })
          }
        })
        cy.layout({ name: 'cose', animate: true } as any).run()
      } catch {
        setTooltip({ key: nodeKey, type: e.target.data('type'), risk: e.target.data('risk') })
      }
    })

    cy.on('tap', 'node', (e: any) => {
      setTooltip({ key: e.target.data('key'), type: e.target.data('type'), risk: e.target.data('risk') })
    })

    cyRef.current = cy
  }

  return (
    <div style={{ height: 'calc(100vh - 49px)', display: 'flex', flexDirection: 'column' }}>
      <div style={{ padding: '10px 24px', background: '#161b22', borderBottom: '1px solid #30363d', display: 'flex', gap: 12, alignItems: 'center' }}>
        <button onClick={() => navigate(-1)} style={{ background: '#21262d', color: '#e6edf3', border: 'none', borderRadius: 6, padding: '6px 12px', cursor: 'pointer' }}>
          ← Назад
        </button>
        <span style={{ color: '#8b949e', fontSize: 13 }}>Граф связей · двойной клик по узлу — раскрыть соседей</span>
        <div style={{ marginLeft: 'auto', display: 'flex', gap: 12, fontSize: 12 }}>
          {[['#da3633', 'Высокий'], ['#d29922', 'Средний'], ['#1f6feb', 'Низкий'], ['#3d8e40', 'Минимальный']].map(([c, l]) => (
            <span key={l}><span style={{ background: c, display: 'inline-block', width: 10, height: 10, borderRadius: 2, marginRight: 4 }} />{l}</span>
          ))}
        </div>
      </div>

      <div style={{ flex: 1, position: 'relative' }}>
        {loading && <p style={{ position: 'absolute', top: 24, left: 24, color: '#8b949e' }}>Загрузка графа...</p>}
        {error && <p style={{ position: 'absolute', top: 24, left: 24, color: '#da3633' }}>{error}</p>}
        <div ref={containerRef} style={{ width: '100%', height: '100%', background: '#0d1117' }} />

        {tooltip && (
          <div style={{
            position: 'absolute', top: 16, right: 16,
            background: '#161b22', border: '1px solid #30363d', borderRadius: 8, padding: 16,
            minWidth: 220,
          }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 8 }}>
              <span style={{ color: '#8b949e', fontSize: 12 }}>Узел</span>
              <button onClick={() => setTooltip(null)} style={{ background: 'none', border: 'none', color: '#8b949e', cursor: 'pointer' }}>✕</button>
            </div>
            <div style={{ fontFamily: 'monospace', fontSize: 12, color: '#79c0ff', marginBottom: 6, wordBreak: 'break-all' }}>{tooltip.key}</div>
            <div style={{ color: '#8b949e', fontSize: 12 }}>Тип: {tooltip.type}</div>
            <div style={{ color: '#8b949e', fontSize: 12 }}>Risk: {(tooltip.risk * 100).toFixed(0)}%</div>
          </div>
        )}
      </div>
    </div>
  )
}
