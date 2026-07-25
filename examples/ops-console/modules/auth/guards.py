"""
Role guards, shared by every controller that needs one.

Guards only ever receive (command, args) — see docs/guards.md — so they read
the session directly from the shared SessionService singleton rather than
through DI. Every protected command must therefore pass a "token" argument,
exactly like the docs/recipes/auth.md pattern this follows.
"""
from __future__ import annotations

from vesper import ForbiddenError

from modules.auth.auth_service import session_service


def require_auth(command: str, args: dict) -> bool:
    """Any logged-in user — admin or viewer."""
    token = args.get("token")
    if session_service.get(token) is None:
        raise ForbiddenError("You must be logged in to do that.")
    return True


def require_admin(command: str, args: dict) -> bool:
    """
    Admin only.

    Raises with a specific message rather than returning False, so the
    frontend's ForbiddenError branch has something more useful to show than
    the generic "Forbidden" — see docs/guards.md's "Raise ForbiddenError
    yourself when you want to deny with a custom message."
    """
    token = args.get("token")
    role = session_service.role(token)
    if role != "admin":
        raise ForbiddenError(
            "This action needs the admin role. "
            f"You are signed in as {role or 'a guest'}."
        )
    return True
