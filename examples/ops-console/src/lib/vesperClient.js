// Thin helpers around the raw `vesper` SDK global.
//
// Every guarded command in this app takes a `token` argument (the pattern
// from docs/recipes/auth.md) — call() adds it automatically so the rest of
// the app never repeats `{ token, ...args }` by hand.

let currentToken = null

export function setToken(token) {
  currentToken = token
}

export function getToken() {
  return currentToken
}

export function call(command, args = {}) {
  return window.vesper.invoke(command, { token: currentToken, ...args })
}

export function callPublic(command, args = {}) {
  return window.vesper.invoke(command, args)
}

// The three IPC failure phases docs/guards.md distinguishes: a policy
// denial (ForbiddenError — the guard ran and said no), a guard bug
// (GuardError — the check itself broke), or the command's own failure
// (anything else). The frontend shows a different message for each rather
// than one generic "Something went wrong."
export function classifyError(err) {
  const name = err && err.name
  if (name === 'ForbiddenError') {
    return { phase: 'policy', label: 'Not allowed', message: err.message }
  }
  if (name === 'GuardError') {
    return { phase: 'guard-bug', label: 'Guard failed unexpectedly', message: err.message }
  }
  return {
    phase: 'command',
    label: 'Action failed',
    message: (err && err.message) || String(err),
  }
}
