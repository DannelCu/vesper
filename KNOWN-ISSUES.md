# Known Issues & Deferred Work

Things that are known, intentional, and worth revisiting — not bugs waiting to be
discovered. Each entry says what the current behaviour is, why it was left that way,
and what would need to change.

---

## Platform coverage that CI cannot verify

The test matrix runs on Linux, macOS and Windows, so everything written in pure
Python — single-instance, window state, path resolution, deep link extraction — is
genuinely exercised on all three.

What CI **cannot** confirm is whether a native API produces its visible effect. A
mocked test proves the code calls `ITaskbarList3` correctly; it cannot prove a
progress bar appears.

| Area | Covered by CI | Not covered |
|---|---|---|
| `badge.set_progress` / `set_badge` | Returns the right value, degrades to no-op | Whether the bar or badge actually renders |
| `clipboard.read_image` / `write_image` | Encoding, data-URL handling, argv shape | A real clipboard round trip |
| `fs.trash` (macOS) | Which command is built | Finder scripting needs automation permission, unavailable in CI |
| `autostart` (Windows / macOS) | Currently mocked | See below — this one **could** be real |
| `power` events (Linux) | Signal mapping, and a real D-Bus round trip for lock/unlock | A real suspend, which would suspend the runner |
| `power` events (Windows / macOS) | Signal mapping only, against mocks | Whether the OS delivers the message at all |

**Deferred:** `autostart` on Windows and macOS is tested against mocks, but both
backends are just a registry value and a plist file. A GitHub runner can perform a
real `enable() → is_enabled() → disable()` round trip on both. Converting those tests
from mocked to real is the highest-value coverage improvement available here.

---

## Single-instance: Windows file permissions are inherited, not enforced

**Current behaviour.** The lock file holding the authentication token is created with
`os.open(..., 0o600)`. On Linux and macOS that mode is applied and the token is
readable only by the owning user.

On Windows the POSIX mode is effectively ignored — Windows uses ACLs. The token file
is protected because it lives under `%LOCALAPPDATA%`, whose default ACLs already
exclude other standard users. The protection is real, but it is *inherited from a
system default* rather than something Vesper sets.

**Why this matters.** Loopback TCP on Windows is machine-wide, not session-scoped.
Under Remote Desktop or fast user switching, another logged-in user's process can
reach the port. The token is what stops it, so the token's confidentiality is doing
real security work.

**Why it was left.** The default ACLs on `%LOCALAPPDATA%` do exclude other standard
users, so the current behaviour is correct on a normally configured machine. Setting
explicit ACLs means `pywin32` or `ctypes` calls into `advapi32`, which is a
meaningful amount of platform code for a gap that only opens up on a machine whose
profile permissions have already been widened.

**What would change it.** Set an explicit DACL on the lock file granting access to
the current user SID only, instead of relying on inheritance. Worth doing if Vesper
is ever used in a multi-user terminal-server deployment.

See [Single Instance](docs/single-instance.md) for the transport design.

---

## Single-instance: a named pipe would be more idiomatic on Windows

**Current behaviour.** All three platforms use a loopback TCP socket, chosen so there
is one transport and one code path. The port is bound to `127.0.0.1` specifically,
which means Windows Defender Firewall does not prompt — it only asks about listeners
on real network interfaces.

**The gap.** The idiomatic Windows solution is a `Local\` named mutex for detection
plus a named pipe for the payload. That avoids sockets entirely: no firewall
question, no listening port for endpoint-protection software to flag, and named pipes
carry their own ACLs rather than relying on a token file.

**Why it was left.** It is a second transport to write and maintain for a problem
that is currently hypothetical. No report of antivirus interference exists yet.

**What would change it.** A user report of EDR or antivirus software flagging the
listening socket. At that point the mutex + named pipe path becomes worth the second
code path.

---

## `xdg-open` does not accept `--`

Not a defect in Vesper, but a constraint worth recording so nobody "fixes" it back.

`shell.reveal()` protects against argument injection by passing an **absolute path**
rather than by using a `--` separator. This is deliberate: `xdg-open`'s argument loop
rejects anything beginning with `-`, including `--` itself:

```console
$ xdg-open -- .
xdg-open: unexpected option '--'
```

Adding a separator would break `reveal()` on Linux rather than harden it. Absolute
paths cannot be mistaken for options on any of the three platforms, so they are the
portable defence. Verified against xdg-open 1.2.1.

---

## Taskbar badges on Windows are drawn, but unverified on real hardware

`badge.set_badge()` now renders the count into an icon with Pillow and applies it
with `ITaskbarList3::SetOverlayIcon`. The rendering was inspected visually and the
COM call is covered by mocked tests, but **no one has yet seen the overlay appear on
a real Windows taskbar** — see the coverage table above for why CI cannot tell us.

Two specific things worth checking on a real machine:

- `_windows_hwnd()` uses `GetForegroundWindow()`, which is this app's window only
  while it has focus. Setting a badge from a background thread while the user is in
  another app would target the wrong window. The progress bar has always had this
  same weakness; the badge inherits it.
- The `.ico` is written to a temp file and loaded with `LoadImageW`, rather than
  built through `CreateIconIndirect`. Simpler and harder to get subtly wrong, but it
  does assume the temp directory is writable.

---

## Unity LauncherEntry is a no-op on most Linux desktops

`badge.*` on Linux speaks the Unity LauncherEntry D-Bus protocol, which KDE Plasma
and GNOME-with-Dash-to-Dock implement, but plain GNOME does not. There is no
cross-desktop standard for this, so there is nothing to fall back to. The functions
return `False` and log once.

---

## `app.quit()` uses a timing heuristic

`App.quit()` defers the window teardown by `_QUIT_DELAY_SECONDS` (50 ms) so that a
call made from inside a command handler can still return its result to the frontend.
Without the delay, PyWebView blocks forever delivering the reply to a destroyed
WebView and the process hangs at interpreter shutdown.

The delay is a heuristic, not a guarantee. Reply delivery is sub-millisecond in
practice, and PyWebView exposes no "response delivered" signal to synchronise on, so
there is no deterministic fix short of patching PyWebView.

Reproduced at a 62% hang rate before the fix and 0% after, across 8 runs each.
