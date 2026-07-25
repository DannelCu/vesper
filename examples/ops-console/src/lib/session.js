// Where the session token lives: the OS keychain when vesper-keychain is
// installed, or a plain module-level variable otherwise — "falls back to
// memory" per the plan, not localStorage. That also means without the
// plugin the session does not survive a reload/restart, and the UI says so
// (see Login.jsx and Settings.jsx).

const KEY = 'session_token'

let memoryToken = null

export async function loadStoredToken(hasKeychain) {
  if (hasKeychain) {
    return window.vesper.keychain.get(KEY)
  }
  return memoryToken
}

export async function storeToken(token, hasKeychain) {
  if (hasKeychain) {
    await window.vesper.keychain.set(KEY, token)
  } else {
    memoryToken = token
  }
}

export async function clearToken(hasKeychain) {
  if (hasKeychain) {
    await window.vesper.keychain.delete(KEY)
  }
  memoryToken = null
}
