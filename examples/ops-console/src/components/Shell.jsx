// App chrome: nav, role badge, unresolved-alert count, logout, and the
// middleware panel toggle. Listens for the native menu (app.menu() in
// app.py) navigating the SPA from outside the page.
import { useEffect, useState } from 'react'
import { useRouter } from '../lib/router'
import { call } from '../lib/vesperClient'
import MiddlewarePanel from './MiddlewarePanel'

const NAV = [
  { path: '/dashboard', label: 'Dashboard' },
  { path: '/processes', label: 'Processes' },
  { path: '/alerts', label: 'Alerts' },
  { path: '/settings', label: 'Settings' },
]

export default function Shell({ session, onLogout, children }) {
  const { path, navigate } = useRouter()
  const [unresolved, setUnresolved] = useState(0)
  const [panelOpen, setPanelOpen] = useState(false)

  useEffect(() => {
    const unsub = window.vesper.on('menu:navigate', ({ path: to }) => navigate(to))
    return unsub
  }, [navigate])

  useEffect(() => {
    let cancelled = false
    async function poll() {
      try {
        const count = await call('alerts.unresolved_count')
        if (!cancelled) setUnresolved(count)
      } catch {
        /* transient — next poll will catch up */
      }
    }
    poll()
    const id = setInterval(poll, 3000)
    return () => {
      cancelled = true
      clearInterval(id)
    }
  }, [])

  return (
    <div className="shell">
      <header className="shell-header">
        <span className="shell-title">Ops Console</span>
        <nav className="shell-nav">
          {NAV.map((item) => (
            <button
              key={item.path}
              className={path.startsWith(item.path) ? 'nav-link active' : 'nav-link'}
              onClick={() => navigate(item.path)}
            >
              {item.label}
              {item.path === '/alerts' && unresolved > 0 && (
                <span className="nav-badge">{unresolved}</span>
              )}
            </button>
          ))}
        </nav>
        <div className="shell-actions">
          <span className={`role-pill role-pill--${session.role}`}>{session.role}</span>
          <span className="shell-username">{session.username}</span>
          <button className="ghost-button" onClick={() => setPanelOpen((v) => !v)}>
            {panelOpen ? 'Hide middleware' : 'Middleware'}
          </button>
          <button className="ghost-button" onClick={onLogout}>
            Log out
          </button>
        </div>
      </header>
      <div className="shell-body">
        <main className="shell-content">{children}</main>
        <MiddlewarePanel open={panelOpen} />
      </div>
    </div>
  )
}
