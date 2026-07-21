"""
Vesper example: a tour of the framework in one file.

Run it with `vesper dev` from this directory. Everything the frontend calls is
defined below — there is no other Python in this example.
"""
from pathlib import Path

from vesper import App

app = App(
    title="Vesper Hello",
    width=820,
    height=640,
    frontend="frontend/index.html",
    debug=True,
    # Confine the filesystem API to this folder. Without a scope the frontend could
    # read anywhere the user can, which is rarely what you want.
    fs_scope=[str(Path(__file__).parent)],
)


@app.command
def greet(name: str) -> str:
    """Called from JS as vesper.invoke("greet", {name}). Plain Python in, string out."""
    return f"Hello, {name or 'world'}!"


@app.command
def system_report() -> dict:
    """Anything JSON-serializable can cross the bridge, including nested dicts."""
    import platform
    import sys

    return {
        "python": sys.version.split()[0],
        "platform": platform.system(),
        "machine": platform.machine(),
    }


@app.command
def read_notes() -> str:
    """
    Read a file through the scoped filesystem API.

    The frontend calls vesper.fs.read() directly for arbitrary paths; this shows the
    other half — a Python command doing the file work and returning just the result.
    """
    notes = Path(__file__).parent / "notes.txt"
    if not notes.exists():
        notes.write_text("Edit me and press Read again.\n", encoding="utf-8")
    return notes.read_text(encoding="utf-8")


@app.command
def save_notes(content: str) -> bool:
    (Path(__file__).parent / "notes.txt").write_text(content, encoding="utf-8")
    return True


@app.on("loaded")
def on_loaded() -> None:
    print("[hello] window loaded")


if __name__ == "__main__":
    app.run()
