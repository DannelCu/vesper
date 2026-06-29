from __future__ import annotations


class Keychain:
    """
    Secure credential store injectable into Vesper services via DI.

    Wraps the OS keychain (Windows Credential Manager, macOS Keychain,
    Linux Secret Service) via the keyring library.

    Declare keychain: Keychain in a service __init__ to receive the
    configured instance registered by KeychainPlugin:

        from vesper import Injectable
        from vesper_keychain import Keychain

        @Injectable()
        class AuthService:
            def __init__(self, keychain: Keychain):
                self.keychain = keychain

            def save_token(self, token: str) -> None:
                self.keychain.set("api_token", token)

            def get_token(self) -> str | None:
                return self.keychain.get("api_token")
    """

    def __init__(self, *, service: str) -> None:
        try:
            import keyring  # noqa: F401
        except ImportError as exc:
            raise RuntimeError(
                "keyring is required by vesper-keychain. "
                "Install it with: pip install keyring"
            ) from exc
        self._service = service

    def get(self, key: str) -> str | None:
        """Return the stored value for key, or None if not found."""
        import keyring
        return keyring.get_password(self._service, key)

    def set(self, key: str, value: str) -> None:
        """Store value under key in the OS keychain."""
        import keyring
        keyring.set_password(self._service, key, value)

    def delete(self, key: str) -> None:
        """Delete key from the OS keychain. No-op if key does not exist."""
        import keyring
        import keyring.errors
        try:
            keyring.delete_password(self._service, key)
        except keyring.errors.PasswordDeleteError:
            pass

    def has(self, key: str) -> bool:
        """Return True if key exists in the OS keychain."""
        return self.get(key) is not None
