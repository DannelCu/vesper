"""
Tests for vesper sync-types (M3.1).

All tests exercise pure logic (type mapping, .d.ts generation) without
spawning real processes. Integration tests create a temporary app.py and
verify the full import → generate → write flow.
"""
from __future__ import annotations

import inspect
import sys
import textwrap
from pathlib import Path
from typing import Dict, List, Optional, Union

import pytest

from vesper.commands.sync_types import (
    _command_args_ts,
    _command_result_ts,
    _get_union_args,
    _import_app,
    _output_path,
    _py_to_ts,
    _return_to_ts,
    generate_dts,
)


# ── _py_to_ts: primitive types ────────────────────────────────────────────────


def test_str_maps_to_string():
    assert _py_to_ts(str) == "string"


def test_int_maps_to_number():
    assert _py_to_ts(int) == "number"


def test_float_maps_to_number():
    assert _py_to_ts(float) == "number"


def test_bool_maps_to_boolean():
    assert _py_to_ts(bool) == "boolean"


def test_none_type_maps_to_null():
    assert _py_to_ts(type(None)) == "null"


def test_empty_annotation_maps_to_unknown():
    assert _py_to_ts(inspect.Parameter.empty) == "unknown"


def test_none_sentinel_maps_to_unknown():
    assert _py_to_ts(None) == "unknown"


# ── _py_to_ts: container types ────────────────────────────────────────────────


def test_bare_list_maps_to_array_unknown():
    assert _py_to_ts(list) == "Array<unknown>"


def test_list_str_maps_to_array_string():
    assert _py_to_ts(List[str]) == "Array<string>"


def test_list_int_maps_to_array_number():
    assert _py_to_ts(List[int]) == "Array<number>"


def test_list_nested():
    assert _py_to_ts(List[List[str]]) == "Array<Array<string>>"


def test_bare_dict_maps_to_record_unknown():
    assert _py_to_ts(dict) == "Record<string, unknown>"


def test_dict_str_int_maps_to_record():
    assert _py_to_ts(Dict[str, int]) == "Record<string, number>"


def test_dict_str_str_maps_to_record():
    assert _py_to_ts(Dict[str, str]) == "Record<string, string>"


# ── _py_to_ts: union / optional ───────────────────────────────────────────────


def test_optional_str_maps_to_string_null():
    assert _py_to_ts(Optional[str]) == "string | null"


def test_optional_int_maps_to_number_null():
    assert _py_to_ts(Optional[int]) == "number | null"


def test_union_str_int():
    assert _py_to_ts(Union[str, int]) == "string | number"


def test_union_str_none():
    assert _py_to_ts(Union[str, None]) == "string | null"


def test_union_multi_plus_none():
    result = _py_to_ts(Union[str, int, None])
    assert result == "(string | number) | null"


# ── _return_to_ts ─────────────────────────────────────────────────────────────


def test_return_none_type_maps_to_void():
    assert _return_to_ts(type(None)) == "void"


def test_return_str_maps_to_string():
    assert _return_to_ts(str) == "string"


def test_return_empty_maps_to_unknown():
    assert _return_to_ts(inspect.Parameter.empty) == "unknown"


# ── _command_args_ts ──────────────────────────────────────────────────────────


def test_no_params_returns_empty_object():
    def cmd():
        pass
    assert _command_args_ts(cmd) == "{}"


def test_typed_params():
    def cmd(name: str, age: int):
        pass
    assert _command_args_ts(cmd) == "{ name: string; age: number }"


def test_untyped_params_fall_back_to_unknown():
    def cmd(x, y):
        pass
    assert _command_args_ts(cmd) == "{ x: unknown; y: unknown }"


def test_optional_param_with_default_uses_question_mark():
    def cmd(name: str = "World"):
        pass
    assert _command_args_ts(cmd) == "{ name?: string }"


def test_required_and_optional_params():
    def cmd(user_id: int, limit: int = 10):
        pass
    assert _command_args_ts(cmd) == "{ user_id: number; limit?: number }"


def test_self_is_excluded():
    class Ctrl:
        def cmd(self, name: str) -> str:
            return name
    instance = Ctrl()
    assert _command_args_ts(instance.cmd) == "{ name: string }"


def test_varargs_are_excluded():
    def cmd(*args, **kwargs):
        pass
    assert _command_args_ts(cmd) == "{}"


# ── _command_result_ts ────────────────────────────────────────────────────────


def test_result_str():
    def cmd() -> str:
        return ""
    assert _command_result_ts(cmd) == "string"


def test_result_none():
    def cmd() -> None:
        pass
    assert _command_result_ts(cmd) == "void"


def test_result_list_str():
    def cmd() -> List[str]:
        return []
    assert _command_result_ts(cmd) == "Array<string>"


def test_result_no_annotation_is_unknown():
    def cmd():
        pass
    assert _command_result_ts(cmd) == "unknown"


# ── generate_dts ──────────────────────────────────────────────────────────────


def test_generate_dts_header():
    def greet(name: str) -> str:
        return ""
    dts = generate_dts({"greet": greet})
    assert "auto-generated" in dts
    assert "do not edit manually" in dts.lower()


def test_generate_dts_contains_interface():
    def greet(name: str) -> str:
        return ""
    dts = generate_dts({"greet": greet})
    assert "interface VesperCommands" in dts


def test_generate_dts_contains_vesper_sdk():
    dts = generate_dts({})
    assert "interface VesperSDK" in dts
    assert "declare const vesper: VesperSDK" in dts


def test_generate_dts_single_command():
    def greet(name: str) -> str:
        return ""
    dts = generate_dts({"greet": greet})
    assert '"greet": { args: { name: string }; result: string }' in dts


def test_generate_dts_sorted_alphabetically():
    def a() -> str: return ""
    def b() -> str: return ""
    def c() -> str: return ""
    dts = generate_dts({"c": c, "a": a, "b": b})
    pos_a = dts.index('"a"')
    pos_b = dts.index('"b"')
    pos_c = dts.index('"c"')
    assert pos_a < pos_b < pos_c


def test_generate_dts_multiple_commands():
    def greet(name: str) -> str: return ""
    def ping() -> None: pass
    dts = generate_dts({"greet": greet, "ping": ping})
    assert '"greet"' in dts
    assert '"ping"' in dts


def test_generate_dts_module_namespaced_commands():
    def find_all() -> List[str]: return []
    dts = generate_dts({"users.find_all": find_all})
    assert '"users.find_all"' in dts


def test_generate_dts_invoke_overloads():
    dts = generate_dts({})
    assert "invoke<T extends keyof VesperCommands>" in dts
    assert "invoke(command: string" in dts


def test_generate_dts_on_method():
    dts = generate_dts({})
    assert "on(event: string" in dts


def test_generate_dts_empty_registry_is_valid():
    dts = generate_dts({})
    assert "interface VesperCommands {\n}" in dts


# ── _output_path ──────────────────────────────────────────────────────────────


def test_vanilla_output_is_frontend(tmp_path):
    path = _output_path(tmp_path, "vanilla")
    assert path == tmp_path / "frontend" / "vesper.d.ts"


def test_react_output_is_src_types(tmp_path):
    path = _output_path(tmp_path, "react")
    assert path == tmp_path / "src" / "types" / "vesper.d.ts"
    assert path.parent.is_dir()


def test_vue_output_is_src_types(tmp_path):
    path = _output_path(tmp_path, "vue")
    assert path == tmp_path / "src" / "types" / "vesper.d.ts"


def test_svelte_output_is_src_types(tmp_path):
    path = _output_path(tmp_path, "svelte")
    assert path == tmp_path / "src" / "types" / "vesper.d.ts"


def test_unknown_template_defaults_like_vanilla(tmp_path):
    path = _output_path(tmp_path, "unknown_template")
    assert path == tmp_path / "frontend" / "vesper.d.ts"


# ── _import_app integration ───────────────────────────────────────────────────


def _write_app(tmp_path: Path, content: str) -> Path:
    app_py = tmp_path / "app.py"
    app_py.write_text(textwrap.dedent(content), encoding="utf-8")
    return app_py


def test_import_app_finds_app_instance(tmp_path):
    entrypoint = _write_app(tmp_path, """
        from vesper import App

        app = App(frontend="frontend/index.html")

        @app.command
        def greet(name: str) -> str:
            return f"Hello, {name}!"

        if __name__ == "__main__":
            app.run()
    """)
    app, error = _import_app(entrypoint, tmp_path)
    assert error is None
    assert app is not None
    assert "greet" in app.registry._commands


def test_import_app_multiple_commands(tmp_path):
    entrypoint = _write_app(tmp_path, """
        from vesper import App

        app = App(frontend="frontend/index.html")

        @app.command
        def ping() -> str:
            return "pong"

        @app.command
        def add(a: int, b: int) -> int:
            return a + b

        if __name__ == "__main__":
            app.run()
    """)
    app, error = _import_app(entrypoint, tmp_path)
    assert error is None
    assert set(app.registry._commands) == {"ping", "add"}


def test_import_app_no_app_instance_returns_error(tmp_path):
    entrypoint = _write_app(tmp_path, "x = 42\n")
    app, error = _import_app(entrypoint, tmp_path)
    assert app is None
    assert error is not None
    assert "No App instance" in error


def test_import_app_syntax_error_returns_error(tmp_path):
    entrypoint = _write_app(tmp_path, "def broken(\n")
    app, error = _import_app(entrypoint, tmp_path)
    assert app is None
    assert error is not None


# ── Python 3.10+ X | Y union (conditional) ───────────────────────────────────


@pytest.mark.skipif(sys.version_info < (3, 10), reason="requires Python 3.10+")
def test_new_union_str_none():
    ann = eval("str | None")  # noqa: S307 — safe, only builds a type
    assert _py_to_ts(ann) == "string | null"


@pytest.mark.skipif(sys.version_info < (3, 10), reason="requires Python 3.10+")
def test_new_union_str_int():
    ann = eval("str | int")  # noqa: S307
    assert _py_to_ts(ann) == "string | number"
