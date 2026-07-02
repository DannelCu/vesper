from vesper_http.client import HttpClient
from vesper_http.plugin import HttpPlugin

Plugin = HttpPlugin

try:
    from importlib.metadata import version as _v
    __version__ = _v("vesper-http")
except Exception:
    __version__ = "0.1.0"

__all__ = ["HttpClient", "HttpPlugin", "Plugin", "__version__"]
