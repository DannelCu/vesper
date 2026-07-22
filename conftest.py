import sys
import threading
from pathlib import Path

import pytest

# Make plugin packages importable from tests without pip-installing them.
_plugins_root = Path(__file__).parent / "plugins"
if _plugins_root.is_dir():
    for _plugin_dir in _plugins_root.iterdir():
        if _plugin_dir.is_dir():
            _src = str(_plugin_dir)
            if _src not in sys.path:
                sys.path.insert(0, _src)


def _loop_threads() -> int:
    return sum(1 for t in threading.enumerate() if t.name == "vesper-async")


@pytest.fixture(autouse=True)
def no_leaked_loop_threads():
    """
    Fail the test that leaks an IPC loop thread, not the one that runs out of
    descriptors four hundred tests later.

    A leaked loop costs three descriptors that nothing reclaims, so the damage
    surfaces far from its cause: the symptom last time was vesper-watch failing
    with EMFILE while its own code was blameless. This puts the failure back on
    the test responsible — close the App, or use ``with App(...) as app``.
    """
    before = _loop_threads()
    yield
    leaked = _loop_threads() - before
    assert leaked <= 0, (
        f"test leaked {leaked} vesper-async thread(s). Close the App it built: "
        "app.close(), or `with App(...) as app:`."
    )
