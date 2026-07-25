import { useEffect, useState } from 'react'
import { call, classifyError } from '../lib/vesperClient'
import ContextMenu from '../components/ContextMenu'
import Banner from '../components/Banner'

export default function Alerts({ path }) {
  const [alerts, setAlerts] = useState([])
  const [menu, setMenu] = useState(null)
  const [toast, setToast] = useState(null)

  const match = path.match(/^\/alerts\/(\d+)/)
  const focusId = match ? Number(match[1]) : null

  async function load() {
    setAlerts(await call('alerts.list'))
  }

  useEffect(() => {
    load()
    const id = setInterval(load, 3000)
    return () => clearInterval(id)
  }, [])

  async function resolve(alert) {
    try {
      await call('alerts.resolve', { alert_id: alert.id })
      load()
    } catch (err) {
      const { label, message } = classifyError(err)
      setToast(`${label}: ${message}`)
    }
  }

  function copyDetail(alert) {
    const when = new Date(alert.triggered_at * 1000).toLocaleString()
    window.vesper.clipboard.write(
      `${alert.metric} = ${alert.value}% (threshold ${alert.threshold}%) at ${when}`
    )
    setToast('Copied alert detail.')
  }

  return (
    <div className="page">
      <h1>Alerts</h1>
      {toast && <Banner kind="info">{toast}</Banner>}
      {alerts.length === 0 && (
        <p className="empty">
          No alerts yet. Lower a threshold in Settings to trigger one quickly.
        </p>
      )}
      <ul className="alert-list">
        {alerts.map((a) => (
          <li
            key={a.id}
            className={[
              'alert-row',
              a.resolved ? 'alert-row--resolved' : '',
              a.id === focusId ? 'alert-row--focused' : '',
            ].join(' ')}
            onContextMenu={(e) => {
              e.preventDefault()
              setMenu({ x: e.clientX, y: e.clientY, alert: a })
            }}
          >
            <span className="alert-metric">
              {a.metric === 'cpu_percent' ? 'CPU' : 'Memory'}
            </span>
            <span className="alert-value">
              {a.value.toFixed(0)}% (threshold {a.threshold.toFixed(0)}%)
            </span>
            <span className="alert-time">
              {new Date(a.triggered_at * 1000).toLocaleTimeString()}
            </span>
            <span className="alert-status">{a.resolved ? 'resolved' : 'open'}</span>
            {!a.resolved && <button onClick={() => resolve(a)}>Resolve</button>}
          </li>
        ))}
      </ul>

      {menu && (
        <ContextMenu
          x={menu.x}
          y={menu.y}
          onClose={() => setMenu(null)}
          items={[
            {
              label: 'Resolve',
              disabled: menu.alert.resolved,
              onSelect: () => resolve(menu.alert),
            },
            { label: 'Copy detail', onSelect: () => copyDetail(menu.alert) },
          ]}
        />
      )}
    </div>
  )
}
