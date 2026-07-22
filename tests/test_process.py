"""Tests for scoped process execution (vesper.core.process)."""
from __future__ import annotations

import subprocess
import sys
import threading
import time
from unittest.mock import MagicMock

import pytest

from vesper import App, ShellScope, ShellScopeError
from vesper.core import process


# ── ShellScope ───────────────────────────────────────────────────────────────


def test_list_form_allows_named_executable_with_any_args():
    scope = ShellScope(["git"])
    assert scope.check(["git", "log", "--oneline"]) == ["git", "log", "--oneline"]


def test_unlisted_executable_is_rejected():
    scope = ShellScope(["git"])
    with pytest.raises(ShellScopeError):
        scope.check(["rm", "-rf", "/"])


def test_empty_argv_is_rejected():
    with pytest.raises(ShellScopeError):
        ShellScope(["git"]).check([])


def test_name_entry_does_not_allow_invocation_by_path(tmp_path):
    """Allowing "git" must not allow running an arbitrary binary named git by path."""
    scope = ShellScope(["git"])
    with pytest.raises(ShellScopeError):
        scope.check([str(tmp_path / "git")])


def test_path_entry_allows_that_resolved_path(tmp_path):
    exe = tmp_path / "tool"
    exe.write_text("")
    scope = ShellScope([str(exe)])
    assert scope.check([str(exe), "arg"])


def test_path_entry_does_not_allow_bare_name(tmp_path):
    scope = ShellScope([str(tmp_path / "tool")])
    with pytest.raises(ShellScopeError):
        scope.check(["tool"])


def test_argument_patterns_gate_each_argument():
    scope = ShellScope({"ffmpeg": ["-i", "*.mp4", "*.webm"]})
    assert scope.check(["ffmpeg", "-i", "in.mp4", "out.webm"])
    with pytest.raises(ShellScopeError):
        scope.check(["ffmpeg", "-i", "in.mp4", "out.avi"])


def test_dict_none_value_allows_any_args():
    scope = ShellScope({"git": None})
    assert scope.check(["git", "push", "--force"])


# ── run() ────────────────────────────────────────────────────────────────────


def _python_scope():
    return ShellScope([sys.executable])


def test_run_without_scope_rejects_and_never_executes(monkeypatch):
    popen = MagicMock()
    monkeypatch.setattr(subprocess, "run", popen)
    monkeypatch.setattr(subprocess, "Popen", popen)

    with pytest.raises(ShellScopeError):
        process.run(["echo", "hi"], scope=None)
    popen.assert_not_called()


def test_run_out_of_scope_never_executes(monkeypatch):
    popen = MagicMock()
    monkeypatch.setattr(subprocess, "run", popen)

    with pytest.raises(ShellScopeError):
        process.run(["echo", "hi"], scope=ShellScope(["git"]))
    popen.assert_not_called()


def test_run_captures_output_and_code():
    result = process.run(
        [sys.executable, "-c", "import sys; print('out'); print('err', file=sys.stderr); sys.exit(3)"],
        scope=_python_scope(),
    )
    assert result["code"] == 3
    assert result["stdout"].strip() == "out"
    assert result["stderr"].strip() == "err"


# ── ProcessManager: spawn / stream / kill ────────────────────────────────────


class _Collector:
    def __init__(self):
        self.events: list[tuple[str, dict]] = []
        self.exited = threading.Event()

    def __call__(self, event, payload):
        self.events.append((event, payload))
        if event == "process:exit":
            self.exited.set()

    def lines(self, event):
        return [p["line"] for e, p in self.events if e == event]


def test_spawn_streams_stdout_and_exit(tmp_path):
    collector = _Collector()
    manager = process.ProcessManager(collector)

    proc_id = manager.spawn(
        [sys.executable, "-u", "-c", "print('one'); print('two')"],
        scope=_python_scope(),
    )

    assert collector.exited.wait(timeout=10)
    assert collector.lines("process:stdout") == ["one", "two"]
    exit_events = [p for e, p in collector.events if e == "process:exit"]
    assert exit_events == [{"id": proc_id, "code": 0}]
    # Exit is the last event a listener sees.
    assert collector.events[-1][0] == "process:exit"


def test_spawn_streams_stderr_separately():
    collector = _Collector()
    manager = process.ProcessManager(collector)

    manager.spawn(
        [sys.executable, "-u", "-c", "import sys; print('boom', file=sys.stderr)"],
        scope=_python_scope(),
    )

    assert collector.exited.wait(timeout=10)
    assert collector.lines("process:stderr") == ["boom"]
    assert collector.lines("process:stdout") == []


def test_kill_terminates_a_long_process():
    collector = _Collector()
    manager = process.ProcessManager(collector)

    proc_id = manager.spawn(
        [sys.executable, "-u", "-c", "import time; print('up', flush=True); time.sleep(60)"],
        scope=_python_scope(),
    )

    # Wait until the process proved it is alive, then kill it.
    deadline = time.monotonic() + 10
    while "up" not in collector.lines("process:stdout"):
        assert time.monotonic() < deadline
        time.sleep(0.05)

    assert manager.kill(proc_id) is True
    assert collector.exited.wait(timeout=10)
    exit_events = [p for e, p in collector.events if e == "process:exit"]
    assert exit_events[0]["id"] == proc_id
    assert exit_events[0]["code"] != 0


def test_kill_unknown_id_is_false():
    manager = process.ProcessManager(lambda *a: None)
    assert manager.kill(999) is False


def test_kill_all_terminates_everything():
    collector = _Collector()
    manager = process.ProcessManager(collector)

    for _ in range(2):
        manager.spawn(
            [sys.executable, "-c", "import time; time.sleep(60)"],
            scope=_python_scope(),
        )

    manager.kill_all()
    deadline = time.monotonic() + 10
    while manager._procs and time.monotonic() < deadline:
        time.sleep(0.05)
    assert not manager._procs


def test_spawn_without_scope_rejects(monkeypatch):
    popen = MagicMock()
    monkeypatch.setattr(subprocess, "Popen", popen)
    manager = process.ProcessManager(lambda *a: None)

    with pytest.raises(ShellScopeError):
        manager.spawn(["sleep", "60"], scope=None)
    popen.assert_not_called()


# ── App wiring ───────────────────────────────────────────────────────────────


def test_process_commands_registered():
    app = App()
    for cmd in ("vesper:process:run", "vesper:process:spawn", "vesper:process:kill"):
        assert cmd in app.registry._commands


def test_app_without_shell_scope_rejects_via_ipc():
    app = App()
    resp = app.ipc.handle({
        "id": "1", "command": "vesper:process:run", "args": {"argv": ["echo", "hi"]},
    })
    assert resp["ok"] is False
    assert resp["error"]["type"] == "ShellScopeError"


def test_app_with_shell_scope_runs_via_ipc():
    app = App(shell_scope=[sys.executable])
    resp = app.ipc.handle({
        "id": "1",
        "command": "vesper:process:run",
        "args": {"argv": [sys.executable, "-c", "print('via ipc')"]},
    })
    assert resp["ok"] is True
    assert resp["result"]["code"] == 0
    assert resp["result"]["stdout"].strip() == "via ipc"


def test_app_accepts_prebuilt_shellscope():
    scope = ShellScope(["git"])
    app = App(shell_scope=scope)
    assert app.shell_scope is scope
