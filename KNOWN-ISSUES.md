# Known Issues & Deferred Work

Things that are known, intentional, and worth revisiting — not bugs waiting to be
discovered. Each entry says what the current behaviour is, why it was left that way,
and what would need to change.

**Deferred is not forgotten.** Everything under [Deferred](#deferred) has a stated
reason for staying open and a stated trigger that would reopen it. Items that have
since been fixed are listed under [Resolved](#resolved) rather than deleted, so the
reasoning stays findable.

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
| `autostart` (Windows / macOS) | Real `enable → is_enabled → disable` round trip | Whether the OS acts on it at login |
| `power` events (Linux) | Signal mapping, and a real D-Bus round trip for lock/unlock | A real suspend, which would suspend the runner |
| `power` events (Windows / macOS) | Signal mapping only, against mocks | Whether the OS delivers the message at all |

---

<a id="deferred"></a>

# Deferred

Open, with a reason. Each of these was looked at and consciously left.

---

## Single-instance: Windows file permissions are inherited, not enforced

**Deferred because:** the inherited `%LOCALAPPDATA%` ACLs are already correct on a normally configured machine, and setting an explicit DACL means `advapi32` calls for a gap that only opens on a profile whose permissions were already widened.

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

**Deferred because:** it is a second transport to write and maintain for a problem that is still hypothetical — no report of antivirus or EDR flagging the loopback listener exists.

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

**Not deferred work** — a platform constraint recorded so nobody "fixes" absolute paths back into a `--` separator that would break `reveal()` on Linux.

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

**Deferred because:** verifying it needs a human looking at a real Windows taskbar, which no CI runner can do. The `_windows_hwnd()` weakness is deferred with it: it predates the badge, affects the progress bar identically, and fixing it means tracking the app's own HWND rather than the foreground one.

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

**Deferred because:** there is nothing to defer *to*. No cross-desktop badge protocol exists, so this is a fact about Linux rather than a gap in Vesper. `capabilities` reports it as N/A with no fix, which is the honest answer.

`badge.*` on Linux speaks the Unity LauncherEntry D-Bus protocol, which KDE Plasma
and GNOME-with-Dash-to-Dock implement, but plain GNOME does not. There is no
cross-desktop standard for this, so there is nothing to fall back to. The functions
return `False` and log once.

---

## `app.quit()` uses a timing heuristic

**Deferred because:** PyWebView exposes no "response delivered" signal to synchronise on, so a deterministic fix means patching PyWebView. Measured at a 0% hang rate as it stands.

`App.quit()` defers the window teardown by `_QUIT_DELAY_SECONDS` (50 ms) so that a
call made from inside a command handler can still return its result to the frontend.
Without the delay, PyWebView blocks forever delivering the reply to a destroyed
WebView and the process hangs at interpreter shutdown.

The delay is a heuristic, not a guarantee. Reply delivery is sub-millisecond in
practice, and PyWebView exposes no "response delivered" signal to synchronise on, so
there is no deterministic fix short of patching PyWebView.

Reproduced at a 62% hang rate before the fix and 0% after, across 8 runs each.

---

<a id="resolved"></a>

# Resolved

Kept rather than deleted, so the reasoning behind the original decision stays
findable when something similar comes up.

---

## ~~The text clipboard raised on Linux without `xclip`~~ — fixed

`clipboard.read()` and `write()` used to let `FileNotFoundError` escape when the
platform tool was absent, while `read_image()` right beside them returned `None`.

**Resolved.** `read()` now returns `""` and `write()` is a no-op, both logging once
at debug — the same contract as `read_image()`. Only `FileNotFoundError` degrades: a
tool that exists and then fails still raises.

The distinction between "no xclip" and "empty clipboard" is not lost. It moved to
where it is actionable — `vesper.capabilities()` and `vesper doctor` — rather than
arriving as an exception across the IPC bridge.

---

## ~~Preflight only covered the tray~~ — fixed

`App._preflight()` could not check `power_events=True`, because there was no
`power_events` capability to check against.

**Resolved.** `capabilities.probe()` now reports it — jeepney on Linux, pyobjc on
macOS, nothing needed on Windows — and the preflight warns for it exactly as it does
for the tray. It is deliberately separate from `keep_awake`: different backends
entirely, a binary versus an importable module.

**Still open within this:** badges are not preflighted. They are never declared on
the `App`, so there is no configuration to compare against — calling `set_badge()` is
the only signal, and that happens long after startup.

---

## ~~Autostart on Windows and macOS was tested against mocks~~ — fixed

Both backends are stdlib — `winreg` and `plistlib` — so a runner can do the real
thing.

**Resolved.** `tests/test_autostart_native.py` performs a real
`enable() → is_enabled() → disable()` round trip on each. The tests use a
pid-suffixed app name so they cannot collide with a real login item, clean up in
fixture teardown so a mid-test failure still tidies up, and skip off their native
platform. The macOS plist is written but never `launchctl load`ed, so nothing is
actually registered to launch.

What this still does not prove is whether the OS acts on the entry at login — that
needs a real login, which is out of reach of any test.

**They immediately earned their keep.** The first CI run failed on Windows:
`_windows_enable()` used `winreg.OpenKey`, which cannot create a key that does not
exist, and the `Run` key does not exist on a profile where nothing has ever
registered a startup entry — every fresh Windows image, GitHub runners included.
Autostart was silently broken there for anyone in that situation. The mocked tests
could not have found it: a `MagicMock` `OpenKey` never raises. Fixed with
`CreateKeyEx`, which opens or creates.
