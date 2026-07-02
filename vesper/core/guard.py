from __future__ import annotations

from collections.abc import Callable


def guard(*guard_fns: Callable) -> Callable[[Callable], Callable]:
    """
    Attach guard functions to a @command method.

    Guards run before global middleware and are fail-safe: a guard must
    return ``True`` or ``None`` to allow the call to proceed. Any other return
    value — including ``False``, ``0``, ``""``, or any other falsy value —
    raises ``ForbiddenError`` and short-circuits the call. Raising an exception
    also short-circuits and propagates as an error response.

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
