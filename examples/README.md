# Vesper Examples

Three runnable apps. Each one is a real application rather than a gallery of buttons —
features appear because the app needs them.

Every example runs **without any optional dependency installed**. Missing ffmpeg, a
missing plugin or a missing `xclip` removes a feature and says so; it never breaks a
screen. That is the contract in [optional-features.md](../docs/optional-features.md),
demonstrated rather than described.

| Example | What it demonstrates | Start here if… |
|---|---|---|
| [hello](hello/) | The whole bridge in one file: commands, arguments, events, scoped file access. Vanilla, ~70 lines of Python. | you have never used Vesper and want the shortest possible complete app. |
| [media-vault](media-vault/) | Why the production localhost server exists — video seeking needs HTTP byte ranges, which `file://` cannot give — and why a `.avi` will not play in a WebView at all, plus converting it on demand with live progress. Also scoped processes (ffmpeg), taskbar progress, multi-window, power events. Vanilla. | you are building anything that plays media, shells out to a binary, or touches a lot of files. |
| [launcher](launcher/) | The shell a Spotlight-style app needs: frameless and transparent with a hand-built drag region, always-on-top, positioned on the active screen, hidden to the tray and summoned by a global hotkey. Plus a calculator that evaluates user input **without `eval()`**. Vanilla. | you are building a tray app, an overlay, a frameless window, or anything that runs a string the user typed. |

Run any of them the same way:

```bash
pip install -e ..        # Vesper, from this repo
cd <example>
vesper dev
```

Each app's README covers its own setup, a guided tour of what to click, which Vesper
feature each part demonstrates, and what degrades without the optional pieces.
