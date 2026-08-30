import { NavLink, Outlet, useNavigate } from 'react-router-dom'
import { useAuth } from '../context/useAuth'

const links = [
  ['/overview', 'Portfolio', 'home'], ['/holdings', 'Holdings', 'briefcase'], ['/trade?side=buy', 'Buy / Sell', 'swap'], ['/analytics', 'Analytics', 'chart'], ['/watchlists', 'Watchlist', 'bookmark'], ['/transactions', 'Transactions', 'activity'],
] as const

function NavIcon({ name }: { name: string }) {
  const paths: Record<string, string> = {
    home: 'M3 11.5 12 4l9 7.5v8a1 1 0 0 1-1 1h-5v-6h-6v6H4a1 1 0 0 1-1-1v-8Z',
    search: 'm20 20-4.5-4.5m2-5a7 7 0 1 1-14 0 7 7 0 0 1 14 0Z',
    bookmark: 'M6 3h12v18l-6-4-6 4V3Z',
    briefcase: 'M8 6V4h8v2m4 4H4v9h16v-9ZM3 10h18',
    activity: 'M4 14h3l2-7 4 11 2-7h5',
    swap: 'M7 7h12m0 0-3-3m3 3-3 3M17 17H5m0 0 3 3m-3-3 3-3',
    chart: 'M4 20V10m5 10V4m5 16v-7m5 7V7',
  }
  return <svg viewBox="0 0 24 24" aria-hidden="true"><path d={paths[name]} /></svg>
}

export function AppShell() {
  const { user, logout } = useAuth()
  const navigate = useNavigate()
  const signOut = () => { logout(); navigate('/login') }
  return <div className="app-shell">
    <aside className="sidebar">
      <NavLink className="brand" to="/portfolio"><span className="brand-mark">S</span><span>StockIt<small>Portfolio tracker</small></span></NavLink>
      <nav className="side-nav" aria-label="Main navigation">{links.map(([to, label, icon]) => <NavLink key={to} to={to}><NavIcon name={icon} /><span>{label}</span></NavLink>)}</nav>
      <div className="sidebar-footer"><div className="avatar">{(user?.name || user?.email || 'U').charAt(0).toUpperCase()}</div><div><strong>{user?.name || 'Investor'}</strong><small>{user?.email}</small></div><button className="logout" onClick={signOut} aria-label="Log out">↗</button></div>
    </aside>
    <div className="content-shell"><header className="topbar"><span className="topbar-context">Portfolio tracker</span><div><span className="topbar-user">{user?.name || user?.email || 'Investor'}</span><button className="logout" onClick={signOut}>Log out</button></div></header><header className="mobile-header"><NavLink className="brand" to="/overview"><span className="brand-mark">S</span> StockIt</NavLink><button className="logout" onClick={signOut}>Log out</button></header><nav className="mobile-nav" aria-label="Mobile navigation">{links.map(([to, label]) => <NavLink key={to} to={to}>{label}</NavLink>)}</nav><main className="page"><Outlet /></main></div>
  </div>
}
