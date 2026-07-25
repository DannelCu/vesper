// Makes the IPC middleware visible: the last commands that ran, how long
// each took, and whether it succeeded — see modules/common/telemetry.py for
// how this is actually assembled (and why app.middleware() alone cannot do
// it, despite what docs/recipes/logging-middleware.md shows).
import { useEffect, useState } from 'react'
import { call } from '../lib/vesperClient'

export default function MiddlewarePanel({ open }) {
  const [entries, setEntries] = useState([])

  useEffect(() => {
    if (!open) return undefined

    let cancelled = false
    async function poll() {
      try {
        const rows = await call('system:middleware_log', { limit: 50 })
        if (!cancelled) setEntries(rows)
      } catch {
        // The panel itself must never break the app it is reporting on.
      }
    }
    poll()
    const id = setInterval(poll, 1500)
    return () => {
      cancelled = true
      clearInterval(id)
    }
  }, [open])

  if (!open) return null

  return (
    <aside className="middleware-panel">
      <h2>IPC middleware</h2>
      <p className="middleware-panel-hint">
        Every command below ran through <code>app.middleware</code> and the
        timing wrapper in <code>modules/common/telemetry.py</code>.
      </p>
      <table>
        <thead>
          <tr>
            <th>Command</th>
            <th>Duration</th>
            <th>Result</th>
          </tr>
        </thead>
        <tbody>
          {entries.map((e, i) => (
            <tr key={i} className={e.ok ? '' : 'row-error'}>
              <td>{e.command}</td>
              <td>{e.duration_ms?.toFixed(1)} ms</td>
              <td>{e.ok ? 'ok' : e.error_type || 'error'}</td>
            </tr>
          ))}
          {entries.length === 0 && (
            <tr>
              <td colSpan={3} className="empty">
                No commands logged yet.
              </td>
            </tr>
          )}
        </tbody>
      </table>
    </aside>
  )
}
