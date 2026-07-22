# Vesper Examples

Four runnable apps. Each one is a real application rather than a gallery of buttons —
features appear because the app needs them.

Every example runs **without any optional dependency installed**. Missing ffmpeg, a
missing plugin or a missing `xclip` removes a feature and says so; it never breaks a
screen. That is the contract in [optional-features.md](../docs/optional-features.md),
demonstrated rather than described.

| Example | What it demonstrates | Start here if… |
|---|---|---|
| [hello](hello/) | The whole bridge in one file: commands, arguments, events, scoped file access. Vanilla, ~70 lines of Python. | you have never used Vesper and want the shortest possible complete app. |
| [media-vault](media-vault/) | Why the production localhost server exists — video seeking needs HTTP byte ranges, which `file://` cannot give. Plus scoped processes (ffmpeg), downloads with taskbar progress, multi-window, power events. Vanilla. | you are building anything that plays media, shells out to a binary, or touches a lot of files. |

Run any of them the same way:

```bash
pip install -e ..        # Vesper, from this repo
cd <example>
vesper dev
```

Each app's README covers its own setup, a guided tour of what to click, which Vesper
feature each part demonstrates, and what degrades without the optional pieces.
