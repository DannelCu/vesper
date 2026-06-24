import pytest
from vesper.core.registry import CommandRegistry
from vesper.exceptions import CommandAlreadyRegisteredError, CommandNotFoundError


def test_register_and_get():
    registry = CommandRegistry()

    def my_cmd():
        return "ok"

    registry.register(my_cmd)
    assert registry.get("my_cmd") is my_cmd


def test_register_uses_function_name():
    registry = CommandRegistry()

    def hello():
        pass

    registry.register(hello)
    assert registry.get("hello") is hello


def test_register_with_explicit_name():
    registry = CommandRegistry()

    def fn():
        pass

    registry.register(fn, name="custom_name")
    assert registry.get("custom_name") is fn


def test_register_explicit_name_not_accessible_by_function_name():
    registry = CommandRegistry()

    def fn():
        pass

    registry.register(fn, name="custom")
    with pytest.raises(CommandNotFoundError):
        registry.get("fn")


def test_duplicate_registration_raises():
    registry = CommandRegistry()

    def fn():
        pass

    registry.register(fn)
    with pytest.raises(CommandAlreadyRegisteredError):
        registry.register(fn)


def test_duplicate_explicit_name_raises():
    registry = CommandRegistry()

    def fn1():
        pass

    def fn2():
        pass

    registry.register(fn1, name="cmd")
    with pytest.raises(CommandAlreadyRegisteredError):
        registry.register(fn2, name="cmd")


def test_get_unknown_command_raises():
    registry = CommandRegistry()
    with pytest.raises(CommandNotFoundError):
        registry.get("does_not_exist")


def test_register_empty_name_raises():
    registry = CommandRegistry()

    def fn():
        pass

    with pytest.raises(ValueError):
        registry.register(fn, name="")


def test_register_whitespace_name_raises():
    registry = CommandRegistry()

    def fn():
        pass

    with pytest.raises(ValueError):
        registry.register(fn, name="   ")


def test_multiple_commands_independent():
    registry = CommandRegistry()

    def cmd_a():
        return "a"

    def cmd_b():
        return "b"

    registry.register(cmd_a)
    registry.register(cmd_b)

    assert registry.get("cmd_a")() == "a"
    assert registry.get("cmd_b")() == "b"