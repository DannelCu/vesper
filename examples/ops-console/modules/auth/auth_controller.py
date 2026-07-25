"""
Login, logout, and "who am I" — the three commands every other guarded
command in this app depends on indirectly (they all check the token this
controller hands out).
"""
from __future__ import annotations

from vesper import Controller, command

from modules.auth.auth_service import SessionService


@Controller("auth")
class AuthController:
    def __init__(self, session: SessionService):
        self.session = session

    @command
    def login(self, username: str, password: str) -> dict:
        result = self.session.login(username, password)
        if result is None:
            raise ValueError("Invalid username or password.")
        return result

    @command
    def logout(self, token: str) -> bool:
        self.session.logout(token)
        return True

    @command
    def me(self, token: str) -> dict | None:
        return self.session.get(token)
