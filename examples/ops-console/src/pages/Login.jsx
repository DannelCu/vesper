import { useState } from 'react'
import { callPublic, setToken } from '../lib/vesperClient'
import { storeToken } from '../lib/session'

export default function Login({ features, onLogin }) {
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)

  async function submit(e) {
    e.preventDefault()
    setBusy(true)
    setError('')
    try {
      const result = await callPublic('auth.login', { username, password })
      setToken(result.token)
      await storeToken(result.token, features.keychain)
      onLogin(result)
    } catch (err) {
      setError(err.message || 'Invalid username or password.')
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="login-screen">
      <form className="login-card" onSubmit={submit}>
        <h1>Ops Console</h1>
        <p className="login-subtitle">Sign in to monitor this machine.</p>

        <label>
          Username
          <input
            value={username}
            onChange={(e) => setUsername(e.target.value)}
            autoFocus
            autoComplete="username"
          />
        </label>
        <label>
          Password
          <input
            type="password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            autoComplete="current-password"
          />
        </label>

        {error && <p className="form-error">{error}</p>}

        <button type="submit" disabled={busy} className="primary-button">
          {busy ? 'Signing in…' : 'Sign in'}
        </button>

        {!features.keychain && (
          <p className="login-hint">
            Session not persisted: install vesper-keychain to keep your login
            between restarts.
          </p>
        )}

        <div className="demo-credentials">
          <p>
            <strong>admin</strong> / <strong>admin</strong> — full access, can
            terminate processes and change thresholds.
          </p>
          <p>
            <strong>viewer</strong> / <strong>viewer</strong> — read-only. Try
            terminating a process from this account — the guard denies it.
          </p>
          <p className="demo-credentials-note">
            Demo credentials only, checked in{' '}
            <code>modules/auth/auth_service.py</code>. A real app would
            verify against a user store or identity provider and issue a
            short-lived, signed token instead of a burned-in dict.
          </p>
        </div>
      </form>
    </div>
  )
}
