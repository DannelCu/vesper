// A hand-rolled SPA router — deliberately no routing library, per the plan
// ("son pocas líneas"). history.pushState + popstate, nothing more.
//
// Works under `serve_frontend=True` because the production static server
// falls back to index.html for extensionless paths (docs/project-config.md)
// — the same reason this app needs that flag at all, alongside media-vault's
// video seek bar.
import { createContext, useCallback, useContext, useEffect, useState } from 'react'

const RouterContext = createContext(null)

function currentPath() {
  return window.location.pathname || '/'
}

export function RouterProvider({ children }) {
  const [path, setPath] = useState(currentPath())

  useEffect(() => {
    function onPopState() {
      setPath(currentPath())
    }
    window.addEventListener('popstate', onPopState)
    return () => window.removeEventListener('popstate', onPopState)
  }, [])

  const navigate = useCallback((to) => {
    if (to === currentPath()) return
    window.history.pushState({}, '', to)
    setPath(to)
  }, [])

  return (
    <RouterContext.Provider value={{ path, navigate }}>{children}</RouterContext.Provider>
  )
}

export function useRouter() {
  const ctx = useContext(RouterContext)
  if (!ctx) throw new Error('useRouter must be used inside <RouterProvider>')
  return ctx
}
