import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import './styles.css'
import App from './App.jsx'

// Right-click menus, page zoom and the rest of security.lockdown() only
// matter in production — never under `vesper dev`, where devtools and
// reload are exactly what you want. lockdown()'s own dev-detection cannot be
// trusted here: it treats *any* http(s) origin on localhost/127.0.0.1 as
// "dev", but this app's production build is ALSO served from
// http://127.0.0.1 (App(serve_frontend=True) — see app.py and
// docs/project-config.md), so the built-in heuristic would silently skip
// lockdown in production too. import.meta.env.DEV — Vite's own build-time
// dev/production flag, true only under `vesper dev` — is what actually tells
// the two apart, and is what makes right-click land on the custom context
// menu (components/ContextMenu.jsx) instead of the engine's own. See
// docs/security-lockdown.md for the full explanation.
if (!import.meta.env.DEV) {
  window.vesper.security.lockdown({ force: true })
}

createRoot(document.getElementById('root')).render(
  <StrictMode>
    <App />
  </StrictMode>
)
