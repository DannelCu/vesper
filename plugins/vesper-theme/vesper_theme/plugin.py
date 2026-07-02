from __future__ import annotations

import threading
from pathlib import Path

from vesper.core.plugin import VesperPlugin


class ThemePlugin(VesperPlugin):
    """
    OS dark/light mode detection plugin for Vesper.

    Detects the current system theme and watches for changes, emitting a
    ``theme:change`` event to the frontend whenever the user switches between
    light and dark mode.

    Note: the CSS ``prefers-color-scheme`` media query already works inside the
    WebView without this plugin — use ThemePlugin when you need to react to
    theme changes from Python (e.g. to swap tray icons, rewrite config, etc.).

    Usage::

        from vesper import App
        from vesper_theme import ThemePlugin

        app = App(plugins=[ThemePlugin()])

    From JavaScript::

        const { theme, is_dark } = await vesper.theme.get()
        vesper.theme.onChange(({ theme, is_dark }) => {
            document.documentElement.classList.toggle("dark", is_dark)
        })
    """

    def __init__(self, *, watch: bool = True) -> None:
        self._watch = watch
        self._app = None

    def register(self, app) -> None:
        self._app = app

        def _get_theme() -> dict:
            import darkdetect
            theme = darkdetect.theme() or "Light"
            return {"theme": theme, "is_dark": theme == "Dark"}

        app.registry.register(_get_theme, name="vesper:theme:get")

        if self._watch:
            def _listener():
                try:
                    import darkdetect

                    def _on_change(theme: str) -> None:
                        if self._app is not None:
                            self._app.window.emit(
                                "theme:change",
                                {"theme": theme, "is_dark": theme == "Dark"},
                            )

                    darkdetect.listener(_on_change)
                except Exception:
                    pass

            t = threading.Thread(target=_listener, daemon=True)
            t.start()

    @classmethod
    def sdk_path(cls) -> Path | None:
        from importlib.resources import files
        return Path(str(files("vesper_theme").joinpath("sdk/vesper-theme.js")))
