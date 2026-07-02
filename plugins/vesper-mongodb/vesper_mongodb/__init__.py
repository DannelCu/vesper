from vesper_mongodb.database import MongoDatabase
from vesper_mongodb.plugin import MongoPlugin

Plugin = MongoPlugin

try:
    from importlib.metadata import version as _v
    __version__ = _v("vesper-mongodb")
except Exception:
    __version__ = "0.1.0"

__all__ = ["MongoDatabase", "MongoPlugin", "Plugin", "__version__"]
