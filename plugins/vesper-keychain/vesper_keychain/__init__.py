from vesper_keychain.keychain import Keychain
from vesper_keychain.plugin import KeychainPlugin

Plugin = KeychainPlugin

try:
    from importlib.metadata import version as _v
    __version__ = _v("vesper-keychain")
except Exception:
    __version__ = "0.1.0"

__all__ = ["Keychain", "KeychainPlugin", "Plugin", "__version__"]
