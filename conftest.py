import sys
from pathlib import Path

# Make plugin packages importable from tests without pip-installing them.
_plugins_root = Path(__file__).parent / "plugins"
if _plugins_root.is_dir():
    for _plugin_dir in _plugins_root.iterdir():
        if _plugin_dir.is_dir():
            _src = str(_plugin_dir)
            if _src not in sys.path:
                sys.path.insert(0, _src)
