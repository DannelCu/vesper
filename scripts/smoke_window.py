#!/usr/bin/env python3
"""
End-to-end smoke test: open a real native window and exercise the IPC bridge.

The unit suite mocks PyWebView, so it passes on machines that cannot open a window
at all. This script is the counterpart — it boots an actual Vesper app in the system
WebView, has the frontend call a Python command, pushes an event back, and verifies
the full round trip before shutting down.

Run it locally, or in CI under a display (xvfb-run on Linux):

    python scripts/smoke_window.py

Exits 0 on success, 1 on failure, with a summary of which steps completed.
"""
from __future__ import annotations

import sys
import tempfile
import threading
import traceback
from pathlib import Path

# Allow running from a source checkout without installing.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from vesper import App  # noqa: E402
from vesper.commands.utils import copy_sdk_to_frontend  # noqa: E402

TIMEOUT_SECONDS = 60

INDEX_HTML = """<!doctype html>
<html>
  <head><meta charset="utf-8"><title>Vesper smoke test</title></head>
  <body>
    <h1>Vesper smoke test</h1>
    <p id="status">starting</p>
    <script src="./vesper.js"></script>
    <script>
      async function main() {
        try {
          const greeting = await vesper.invoke("smoke_ping", { value: 41 });
          document.getElementById("status").textContent = greeting;

          // Report what the frontend actually received, so a silently wrong
          // result fails the run instead of passing as "no exception raised".
          await vesper.invoke("smoke_report", { received: greeting });
        } catch (error) {
          await vesper.invoke("smoke_report", { received: "JS error: " + error });
        }
      }
      window.addEventListener("load", main);
    </script>
  </body>
</html>
"""


def main() -> int:
    results: dict[str, object] = {
        "window_loaded": False,
        "command_called": False,
        "event_received": None,
    }

    project_dir = Path(tempfile.mkdtemp(prefix="vesper-smoke-"))
    frontend_dir = project_dir / "frontend"
    frontend_dir.mkdir()
    (frontend_dir / "index.html").write_text(INDEX_HTML, encoding="utf-8")
    copy_sdk_to_frontend(frontend_dir)

    app = App(
        title="Vesper Smoke Test",
        width=480,
        height=320,
        frontend=str(frontend_dir / "index.html"),
    )

    @app.command("smoke_ping")
    def smoke_ping(value: int) -> str:
        results["command_called"] = True
        return f"pong:{value + 1}"

    @app.command("smoke_report")
    def smoke_report(received: str) -> None:
        results["event_received"] = received
        # Quitting from inside a command is the case that used to hang the process at
        # shutdown, so exercising it here is the point: App.quit() defers the teardown
        # far enough for this call's reply to reach the WebView.
        app.quit()

    @app.on("loaded")
    def on_loaded() -> None:
        results["window_loaded"] = True

    # A hung WebView would otherwise block CI until the job-level timeout. Force the
    # window down instead, so the failure is reported with the steps that did complete.
    def watchdog() -> None:
        print(f"TIMEOUT: no IPC round trip within {TIMEOUT_SECONDS}s", file=sys.stderr)
        try:
            app.quit()
        except Exception:
            traceback.print_exc()

    timer = threading.Timer(TIMEOUT_SECONDS, watchdog)
    timer.daemon = True
    timer.start()

    try:
        app.run()
    finally:
        timer.cancel()

    ok = (
        results["window_loaded"]
        and results["command_called"]
        and results["event_received"] == "pong:42"
    )

    print("")
    print("Vesper Window Smoke Test")
    print("========================")
    print(f"[{'OK' if results['window_loaded'] else 'FAIL'}] window opened and loaded")
    print(f"[{'OK' if results['command_called'] else 'FAIL'}] JS invoked Python command")
    print(
        f"[{'OK' if results['event_received'] == 'pong:42' else 'FAIL'}] "
        f"IPC returned correct value (got: {results['event_received']!r})"
    )
    print("")

    if not ok:
        print("Smoke test failed.")
        return 1

    print("Smoke test passed.")
    return 0


if __name__ == "__main__":
    exit_code = main()

    sys.exit(exit_code)
