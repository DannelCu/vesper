import { useEffect, useState } from 'react'
import { RouterProvider, useRouter } from './lib/router'
import { loadFeatures } from './lib/features'
import { loadStoredToken, clearToken } from './lib/session'
import { setToken, call, callPublic } from './lib/vesperClient'
import { initTheme } from './lib/theme'
import Login from './pages/Login'
import Dashboard from './pages/Dashboard'
import Processes from './pages/Processes'
import Alerts from './pages/Alerts'
import Settings from './pages/Settings'
import Shell from './components/Shell'

function Routes({ path, session, features }) {
  if (path.startsWith('/processes')) return <Processes />
  if (path.startsWith('/alerts')) return <Alerts path={path} />
  if (path.startsWith('/settings')) return <Settings session={session} features={features} />
  return <Dashboard />
}

function Boot() {
  const { path, navigate } = useRouter()
  const [features, setFeatures] = useState(null)
  const [session, setSession] = useState(null)
  const [booting, setBooting] = useState(true)

  useEffect(() => {
    let unsubDeeplink
    let unsubNotifyAction

    function routeDeepLink(url) {
      // vesper-ops://alert/<id> — hostname is "alert", pathname is "/<id>",
      // same split as Python's urlparse().netloc / .path (see app.py).
      try {
        const parsed = new URL(url)
        if (parsed.hostname === 'alert') {
          navigate(`/alerts${parsed.pathname}`)
        }
      } catch {
        // Not a URL we understand — ignore rather than crash the boot.
      }
    }

    async function boot() {
      const feats = await loadFeatures()
      setFeatures(feats)
      await initTheme(feats.theme)

      // Live event, plus the one-shot pull for a link that arrived before
      // this listener existed (see system:pending_deeplink in app.py).
      unsubDeeplink = window.vesper.on('deeplink', ({ url }) => routeDeepLink(url))
      const pending = await callPublic('system:pending_deeplink')
      if (pending) routeDeepLink(pending)

      // The rich notification's "View" button (vesper-notify only — see
      // app.py's _notify_alert_map). Its own click/action events carry only
      // the notification's own id, not app data, so this asks the backend
      // which alert that id was about.
      if (feats.notify) {
        unsubNotifyAction = window.vesper.on('notify:action', async ({ id }) => {
          const alertId = await callPublic('system:alert_for_notification', { notify_id: id })
          if (alertId != null) navigate(`/alerts/${alertId}`)
        })
      }

      const stored = await loadStoredToken(feats.keychain)
      if (stored) {
        setToken(stored)
        // The backend's SessionService is in-memory only, so this only
        // succeeds within the same running process — see the README's note
        // on why keychain persistence and backend session state are two
        // separate things this app does not fully combine.
        const me = await callPublic('auth.me', { token: stored })
        if (me) {
          setSession(me)
        } else {
          await clearToken(feats.keychain)
          setToken(null)
        }
      }
      setBooting(false)
    }

    boot()
    return () => {
      unsubDeeplink && unsubDeeplink()
      unsubNotifyAction && unsubNotifyAction()
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  useEffect(() => {
    if (session && path === '/') navigate('/dashboard')
  }, [session, path, navigate])

  async function handleLogout() {
    try {
      await call('auth.logout')
    } catch {
      // Best-effort — the local session is cleared either way below.
    }
    await clearToken(features?.keychain)
    setToken(null)
    setSession(null)
    navigate('/')
  }

  if (booting) return <div className="boot-screen">Loading…</div>
  if (!session) return <Login features={features} onLogin={setSession} />

  return (
    <Shell session={session} onLogout={handleLogout}>
      <Routes path={path} session={session} features={features} />
    </Shell>
  )
}

export default function App() {
  return (
    <RouterProvider>
      <Boot />
    </RouterProvider>
  )
}
