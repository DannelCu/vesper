from __future__ import annotations

import inspect
import typing
from collections.abc import Callable
from typing import Any


def Injectable() -> Callable[[type], type]:
    """Mark a class as injectable — available as a DI provider."""
    def decorator(cls: type) -> type:
        cls.__vesper_injectable__ = True
        return cls
    return decorator


def Controller(
    prefix: str = "",
    *,
    guards: list | None = None,
) -> Callable[[type], type]:
    """
    Mark a class as a Vesper controller.

    Args:
        prefix: IPC namespace prefix. Commands register as
                "<prefix>.<name>" when prefix is non-empty.
        guards: Guard functions applied to every command in this
                controller, evaluated before method-level guards.
    """
    def decorator(cls: type) -> type:
        cls.__vesper_controller__ = {"prefix": prefix, "guards": guards or []}
        return cls
    return decorator


def command(
    target: Callable | str | None = None,
    *,
    name: str | None = None,
) -> Callable:
    """
    Mark a controller method as an IPC command.

    Supports all three forms:
        @command
        @command("customName")
        @command(name="customName")
    """

    def _mark(fn: Callable) -> Callable:
        fn.__vesper_command__ = {"name": name or fn.__name__}
        return fn

    if callable(target):
        return _mark(target)

    if isinstance(target, str):
        if name is not None:
            raise ValueError("Command name cannot be provided twice.")
        _name = target

        def _str_decorator(fn: Callable) -> Callable:
            fn.__vesper_command__ = {"name": _name}
            return fn

        return _str_decorator

    if target is not None:
        raise TypeError("@command expects a function, a name string, or no argument.")

    return _mark


class Container:
    """
    Minimal IoC container.

    Resolves providers as singletons by inspecting __init__ type annotations.
    Only resolves parameters whose annotation is a concrete type — skips
    primitives and unannotated params.

    Plugins can register globally-available instances via register_global()
    so they are injectable into any module's services without being listed
    in the module's providers.
    """

    _global: dict[type, Any] = {}

    @classmethod
    def register_global(cls, type_: type, instance: Any) -> None:
        """Register a globally-available provider instance (e.g. from a plugin)."""
        cls._global[type_] = instance

    @classmethod
    def clear_global(cls) -> None:
        """Remove all globally-registered providers. Useful in tests."""
        cls._global.clear()

    def __init__(self, providers: list[type]) -> None:
        self._providers: set[type] = set(providers)
        self._singletons: dict[type, Any] = {}

    def resolve(self, cls: type) -> Any:
        if cls in self._singletons:
            return self._singletons[cls]

        if cls in Container._global:
            return Container._global[cls]

        deps: dict[str, Any] = {}
        try:
            hints = typing.get_type_hints(cls.__init__)
            for param_name, param in inspect.signature(cls.__init__).parameters.items():
                if param_name == "self":
                    continue
                ann = hints.get(param_name, inspect.Parameter.empty)
                if ann is inspect.Parameter.empty:
                    continue
                if isinstance(ann, type):
                    deps[param_name] = self.resolve(ann)
        except (ValueError, TypeError, NameError):
            pass

        instance = cls(**deps)
        self._singletons[cls] = instance
        return instance


def Module(
    *,
    controllers: list[type] | None = None,
    providers: list[type] | None = None,
    imports: list[type] | None = None,
) -> Callable[[type], type]:
    """
    Define a Vesper module — a self-contained feature unit.

    Args:
        controllers: @Controller classes whose @command methods become IPC endpoints.
        providers:   @Injectable classes available for DI within this module.
        imports:     Other @Module classes to register alongside this one.
    """
    def decorator(cls: type) -> type:
        cls.__vesper_module__ = {
            "controllers": controllers or [],
            "providers": providers or [],
            "imports": imports or [],
        }
        return cls
    return decorator
