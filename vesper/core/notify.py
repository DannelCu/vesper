from __future__ import annotations

import subprocess
import sys
import threading


def _ps_escape(s: str) -> str:
    # Strip control characters (keep printable + tab); remove newlines.
    s = "".join(c for c in s if c >= " " or c == "\t")
    # Escape single-quotes (the only meaningful escape inside PS single-quoted strings).
    return s.replace("'", "''")


def _notify_windows(title: str, body: str) -> None:
    t = _ps_escape(title)
    b = _ps_escape(body)
    script = (
        "Add-Type -AssemblyName System.Windows.Forms;"
        "$n=[System.Windows.Forms.NotifyIcon]::new();"
        "$n.Icon=[System.Drawing.SystemIcons]::Information;"
        "$n.Visible=$true;"
        f"$n.ShowBalloonTip(3000,'{t}','{b}',[System.Windows.Forms.ToolTipIcon]::Info);"
        "Start-Sleep -Milliseconds 3500;"
        "$n.Dispose()"
    )
    subprocess.run(
        ["powershell", "-WindowStyle", "Hidden", "-Command", script],
        capture_output=True,
        check=False,
    )


def _notify_macos(title: str, body: str) -> None:
    t = title.replace('"', '\\"').replace("\n", " ")
    b = body.replace('"', '\\"').replace("\n", " ")
    subprocess.run(
        ["osascript", "-e", f'display notification "{b}" with title "{t}"'],
        capture_output=True,
        check=False,
    )


def _notify_linux(title: str, body: str) -> None:
    subprocess.run(["notify-send", title, body], capture_output=True, check=False)


def send(title: str, body: str = "") -> None:
    """Send a native desktop notification in a background thread (fire-and-forget)."""
    if sys.platform == "win32":
        fn = _notify_windows
    elif sys.platform == "darwin":
        fn = _notify_macos
    else:
        fn = _notify_linux

    threading.Thread(target=fn, args=(title, body), daemon=True).start()
