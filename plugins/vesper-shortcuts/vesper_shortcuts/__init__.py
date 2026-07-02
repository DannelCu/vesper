from vesper_shortcuts.plugin import ShortcutsPlugin

Plugin = ShortcutsPlugin

try:
    from importlib.metadata import version as _v
    __version__ = _v("vesper-shortcuts")
except Exception:
    __version__ = "0.1.0"

__all__ = ["ShortcutsPlugin", "Plugin", "__version__"]
