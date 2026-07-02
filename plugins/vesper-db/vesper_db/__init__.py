from vesper_db.base import Base
from vesper_db.session import DbSession
from vesper_db.plugin import DatabasePlugin

Plugin = DatabasePlugin

try:
    from importlib.metadata import version as _v
    __version__ = _v("vesper-db")
except Exception:
    __version__ = "0.1.0"

__all__ = ["Base", "DbSession", "DatabasePlugin", "Plugin", "__version__"]
