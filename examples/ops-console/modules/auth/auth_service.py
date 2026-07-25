"""
Session state for ops-console: two burned-in demo accounts, a role each,
and an in-memory token store.

A real app would check a hashed password against a user store (or an
identity provider) and issue a signed/expiring token — see the note on
DEMO_USERS below. This recipe is deliberately the simple version from
docs/recipes/auth.md: a dict, a secrets.token_hex() token, and a role string.

SessionService is registered as a global DI provider (see app.py) so
AuthController receives this exact instance — and so do the guards in
guards.py, which read it directly rather than through the container, because
guards only ever receive (command, args), never an injected service
(see docs/guards.md).
"""
from __future__ import annotations

import hashlib
import secrets

from vesper import Injectable

# Demo credentials, intentionally burned into source — see the README's
# "Credentials" section for why, and what a real app would do instead.
DEMO_USERS: dict[str, dict] = {
    "admin": {
        "password_hash": hashlib.sha256(b"admin").hexdigest(),
        "role": "admin",
    },
    "viewer": {
        "password_hash": hashlib.sha256(b"viewer").hexdigest(),
        "role": "viewer",
    },
}


@Injectable()
class SessionService:
    """Who is logged in, with what role, keyed by an opaque bearer token."""

    def __init__(self) -> None:
        self._sessions: dict[str, dict] = {}

    def login(self, username: str, password: str) -> dict | None:
        user = DEMO_USERS.get(username)
        if user is None:
            return None
        if hashlib.sha256(password.encode()).hexdigest() != user["password_hash"]:
            return None

        token = secrets.token_hex(32)
        self._sessions[token] = {"username": username, "role": user["role"]}
        return {"token": token, "username": username, "role": user["role"]}

    def logout(self, token: str) -> None:
        self._sessions.pop(token, None)

    def get(self, token: str | None) -> dict | None:
        if not token:
            return None
        return self._sessions.get(token)

    def role(self, token: str | None) -> str | None:
        session = self.get(token)
        return session["role"] if session else None


# The one instance the whole app shares: injected into AuthController via
# app.register_global_provider(SessionService, session_service) in app.py,
# and imported directly by guards.py, which sits outside the DI graph.
session_service = SessionService()
