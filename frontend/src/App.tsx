import { BrowserRouter, Routes, Route, NavLink } from 'react-router-dom'
import Feed from './pages/Feed'
import GraphPage from './pages/Graph'
import ObjectCard from './pages/ObjectCard'
import Cases from './pages/Cases'

const nav: React.CSSProperties = {
  display: 'flex', gap: 24, padding: '12px 24px',
  background: '#161b22', borderBottom: '1px solid #30363d',
  alignItems: 'center',
}

const logo: React.CSSProperties = {
  fontWeight: 700, fontSize: 18, color: '#58a6ff', marginRight: 'auto', letterSpacing: 1,
}

export default function App() {
  return (
    <BrowserRouter>
      <nav style={nav}>
        <span style={logo}>⬡ Digital Shadow</span>
        <NavLink to="/" style={linkStyle} end>Лента сигналов</NavLink>
        <NavLink to="/cases" style={linkStyle}>Дела</NavLink>
      </nav>
      <Routes>
        <Route path="/" element={<Feed />} />
        <Route path="/objects/:id" element={<ObjectCard />} />
        <Route path="/graph/:id" element={<GraphPage />} />
        <Route path="/cases" element={<Cases />} />
      </Routes>
    </BrowserRouter>
  )
}

function linkStyle({ isActive }: { isActive: boolean }): React.CSSProperties {
  return {
    color: isActive ? '#58a6ff' : '#8b949e',
    textDecoration: 'none',
    fontWeight: isActive ? 600 : 400,
    fontSize: 14,
  }
}
