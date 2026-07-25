import { useEffect, useState } from 'react'
import { call, classifyError } from '../lib/vesperClient'
import Banner from '../components/Banner'

export default function Settings({ session, features }) {
  const [form, setForm] = useState({ cpu_percent: 80, mem_percent: 85, duration_seconds: 5 })
  const [error, setError] = useState('')
  const [saved, setSaved] = useState(false)

  useEffect(() => {
    call('alerts.get_thresholds').then(setForm)
  }, [])

  const isAdmin = session.role === 'admin'

  async function save(e) {
    e.preventDefault()
    setError('')
    setSaved(false)
    try {
      const updated = await call('alerts.set_thresholds', form)
      setForm(updated)
      setSaved(true)
    } catch (err) {
      const { label, message } = classifyError(err)
      setError(`${label}: ${message}`)
    }
  }

  function field(key, label, min) {
    return (
      <label>
        {label}
        <input
          type="number"
          min={min}
          disabled={!isAdmin}
          value={form[key]}
          onChange={(e) => setForm((f) => ({ ...f, [key]: Number(e.target.value) }))}
        />
      </label>
    )
  }

  return (
    <div className="page">
      <h1>Settings</h1>

      <section>
        <h2>Alert thresholds</h2>
        {!isAdmin && (
          <Banner kind="info">
            Read-only — the viewer role cannot change thresholds.
          </Banner>
        )}
        <form className="settings-form" onSubmit={save}>
          {field('cpu_percent', 'CPU % threshold', 1)}
          {field('mem_percent', 'Memory % threshold', 1)}
          {field('duration_seconds', 'Sustained for (seconds)', 0)}
          {isAdmin && (
            <button type="submit" className="primary-button">
              Save
            </button>
          )}
          {error && <p className="form-error">{error}</p>}
          {saved && <p className="form-success">Saved.</p>}
        </form>
      </section>

      <section>
        <h2>Optional pieces on this machine</h2>
        <table className="data-table">
          <tbody>
            <tr>
              <td>Session persistence (vesper-keychain)</td>
              <td>{features.keychain ? 'active' : 'in memory only'}</td>
            </tr>
            <tr>
              <td>Live metrics (vesper-sysinfo)</td>
              <td>{features.sysinfo ? 'active' : 'synthetic data'}</td>
            </tr>
            <tr>
              <td>Metrics history (vesper-db)</td>
              <td>{features.db ? 'persisted across restarts' : 'this session only'}</td>
            </tr>
            <tr>
              <td>Rich notifications (vesper-notify)</td>
              <td>{features.notify ? 'active' : 'core notify() fallback'}</td>
            </tr>
            <tr>
              <td>System theme (vesper-theme)</td>
              <td>{features.theme ? 'following OS' : 'fixed light'}</td>
            </tr>
            <tr>
              <td>Crash reporting (vesper-crash)</td>
              <td>
                {features.crash
                  ? 'installed, inactive without SENTRY_DSN'
                  : 'not installed'}
              </td>
            </tr>
            <tr>
              <td>Process table (psutil)</td>
              <td>{features.psutil ? 'available' : 'not installed'}</td>
            </tr>
          </tbody>
        </table>
      </section>
    </div>
  )
}
