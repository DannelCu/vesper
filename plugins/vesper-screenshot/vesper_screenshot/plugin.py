from __future__ import annotations

import base64
import os
import sys
from pathlib import Path

from vesper.core.plugin import VesperPlugin

_PNG_PREFIX = "data:image/png;base64,"


class ScreenshotPlugin(VesperPlugin):
    """
    Screen capture for Vesper via mss: the full virtual screen, one monitor,
    or a region — returned as a PNG data URL or written to a scope-validated
    path.

    Known limits, surfaced as explanatory errors rather than opaque tracebacks:

    - **Wayland**: mss reads X11/XRandR; under a pure Wayland session there is
      nothing for it to read. Captures fail with a clear message. The XDG
      desktop portal would be the correct route and may become one later.
    - **macOS**: captures require the Screen Recording permission, granted
      manually in System Settings → Privacy & Security → Screen Recording (the
      OS prompts on first attempt; a change requires restarting the app).
      Without it, captures return a black/empty image or fail.

    Usage::

        from vesper_screenshot import ScreenshotPlugin

        app = App(plugins=[ScreenshotPlugin()])
    """

    def __init__(self) -> None:
        self._app = None

    def register(self, app) -> None:
        self._app = app

        def _capture(monitor: int = 0, region: dict | None = None, dest: str = "") -> str:
            return self.capture(monitor=monitor, region=region, dest=dest or None)

        def _monitors() -> list:
            return self.monitors()

        app.registry.register(_capture, name="vesper:screenshot:capture")
        app.registry.register(_monitors, name="vesper:screenshot:monitors")

    def _check_supported(self) -> None:
        if (
            sys.platform.startswith("linux")
            and os.environ.get("XDG_SESSION_TYPE", "").lower() == "wayland"
        ):
            raise RuntimeError(
                "Screen capture is unavailable under Wayland: mss reads X11, which "
                "a pure Wayland session does not expose. This is a known limit of "
                "the plugin (the XDG desktop portal is the eventual route). "
                "An XWayland or X11 session works."
            )

    def monitors(self) -> list[dict]:
        """Monitor geometry as mss reports it. Index 0 is the whole virtual screen."""
        self._check_supported()
        import mss

        with mss.mss() as sct:
            return [dict(m) for m in sct.monitors]

    def capture(
        self,
        *,
        monitor: int = 0,
        region: dict | None = None,
        dest: str | None = None,
    ) -> str:
        """
        Capture the screen.

        Args:
            monitor: mss monitor index — 0 is the whole virtual screen,
                     1..N the individual monitors.
            region:  ``{"left", "top", "width", "height"}`` in pixels;
                     overrides *monitor*.
            dest:    Write the PNG to this path (validated against the app's
                     ``fs_scope``) and return the path. Without it, returns a
                     ``data:image/png;base64,...`` URL.
        """
        self._check_supported()
        import mss
        import mss.tools

        try:
            with mss.mss() as sct:
                if region is not None:
                    target = {
                        "left": int(region["left"]),
                        "top": int(region["top"]),
                        "width": int(region["width"]),
                        "height": int(region["height"]),
                    }
                else:
                    if not 0 <= monitor < len(sct.monitors):
                        raise ValueError(
                            f"Monitor index {monitor} out of range "
                            f"(0..{len(sct.monitors) - 1})."
                        )
                    target = sct.monitors[monitor]

                shot = sct.grab(target)
                png = mss.tools.to_png(shot.rgb, shot.size)
        except Exception as e:
            if isinstance(e, (ValueError, RuntimeError)):
                raise
            raise RuntimeError(self._explain_failure(e)) from e

        if dest is not None:
            scope = getattr(self._app, "fs_scope", None)
            dest_path = Path(scope.check(dest)) if scope is not None else Path(dest)
            dest_path.parent.mkdir(parents=True, exist_ok=True)
            dest_path.write_bytes(png)
            return str(dest_path)

        return _PNG_PREFIX + base64.b64encode(png).decode("ascii")

    @staticmethod
    def _explain_failure(error: Exception) -> str:
        if sys.platform == "darwin":
            return (
                f"Screen capture failed ({error}). On macOS this usually means the "
                "Screen Recording permission is missing: System Settings → Privacy "
                "& Security → Screen Recording, enable this app, then restart it."
            )
        return f"Screen capture failed: {error}"

    @classmethod
    def sdk_path(cls) -> Path | None:
        from importlib.resources import files
        return Path(str(files("vesper_screenshot").joinpath("sdk/vesper-screenshot.js")))
