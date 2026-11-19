import { NavLink, Outlet } from 'react-router-dom'

export const NAV = [
  { to: '/', label: 'Home', icon: '⌂', end: true },
  { to: '/predict', label: 'Predict', icon: '◎' },
  { to: '/data-explorer', label: 'Data Explorer', icon: '▥' },
  { to: '/model-performance', label: 'Model Performance', icon: '✓' },
  { to: '/insights', label: 'Insights', icon: '✦' },
  { to: '/planning', label: 'Workforce Planning', icon: '⚖' },
  { to: '/about', label: 'About', icon: 'ⓘ' },
]

export default function Layout() {
  return (
    <div className="app">
      <aside className="sidebar">
        <div className="brand">Absenteeism Intelligence</div>
        <nav className="nav" aria-label="Main">
          {NAV.map(n => (
            <NavLink key={n.to} to={n.to} end={n.end} className={({ isActive }) => (isActive ? 'active' : undefined)}>
              <span aria-hidden="true">{n.icon}</span>{n.label}
            </NavLink>
          ))}
        </nav>
        <p className="side-note">Historical data from one company. Estimates support planning conversations; they are not certainties about people.</p>
      </aside>
      <main className="main"><Outlet /></main>
    </div>
  )
}
