from vesper_store.plugin import StorePlugin

Plugin = StorePlugin

try:
    from importlib.metadata import version as _v
    __version__ = _v("vesper-store")
except Exception:
    __version__ = "0.1.0"

__all__ = ["StorePlugin", "Plugin", "__version__"]
