from vesper_theme.plugin import ThemePlugin

Plugin = ThemePlugin

try:
    from importlib.metadata import version as _v
    __version__ = _v("vesper-theme")
except Exception:
    __version__ = "0.1.0"

__all__ = ["ThemePlugin", "Plugin", "__version__"]
