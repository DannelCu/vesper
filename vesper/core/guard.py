from __future__ import annotations

from collections.abc import Callable


def guard(*guard_fns: Callable) -> Callable[[Callable], Callable]:
    """
    Attach guard functions to a @command method.

    Guards run before global middleware. A guard returning False yields a
    ForbiddenError response; raising an exception propagates it as an error
    response; returning True or None allows the call to proceed.

    Usage — single guard:
        @command
        @guard(is_authenticated)
        def get_profile(self) -> dict: ...

    Usage — multiple guards (all must pass, evaluated left to right):
        @command
        @guard(is_authenticated, is_admin)
        def delete_user(self, id: int) -> bool: ...

    Usage — stacked decorators (outermost runs first):
        @command
        @guard(is_authenticated)
        @guard(is_admin)
        def secret(self) -> str: ...

    Async guard functions are also supported:
        async def rate_limit(command: str, args: dict) -> bool:
            return await check_rate_limit()
    """
    def decorator(fn: Callable) -> Callable:
        existing: list[Callable] = getattr(fn, "__vesper_guards__", [])
        fn.__vesper_guards__ = list(guard_fns) + existing
        return fn
    return decorator
