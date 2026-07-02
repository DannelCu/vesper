from __future__ import annotations

from pathlib import Path

from vesper.core.plugin import VesperPlugin
from vesper_keychain.keychain import Keychain


class KeychainPlugin(VesperPlugin):
    """
    Secure OS keychain plugin for Vesper.

    Stores sensitive data (API keys, tokens, passwords) in the OS keychain
    instead of plain files. Uses the keyring library for cross-platform support:
      - Windows: Windows Credential Manager
      - macOS:   Keychain
      - Linux:   Secret Service API (requires secretstorage or kwallet)

    Usage:
        from vesper import App
        from vesper_keychain import KeychainPlugin

        app = App(
            root_module=AppModule,
            plugins=[KeychainPlugin(service="my-app")],
        )

    Services receive the keychain via DI:
        from vesper import Injectable
        from vesper_keychain import Keychain

        @Injectable()
        class AuthService:
            def __init__(self, keychain: Keychain):
                self.keychain = keychain

            def save_token(self, token: str) -> None:
                self.keychain.set("api_token", token)

    JS can also call the commands directly:
        await vesper.keychain.set("api_token", "sk-...")
        const token = await vesper.keychain.get("api_token")
    """

    def __init__(self, *, service: str = "vesper-app") -> None:
        self._service = service

    def register(self, app) -> None:
        keychain = Keychain(service=self._service)

        app.register_global_provider(Keychain, keychain)

        @app.command("keychain:get")
        def get(key: str) -> str | None:
            return keychain.get(key)

        @app.command("keychain:set")
        def set_(key: str, value: str) -> None:
            keychain.set(key, value)

        @app.command("keychain:delete")
        def delete(key: str) -> None:
            keychain.delete(key)

        @app.command("keychain:has")
        def has(key: str) -> bool:
            return keychain.has(key)

    @classmethod
    def sdk_path(cls) -> Path | None:
        from importlib.resources import files
        return Path(str(files("vesper_keychain").joinpath("sdk/vesper-keychain.js")))
