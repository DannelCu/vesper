"""Tests that App._global_providers is isolated per App instance."""
from __future__ import annotations

from vesper import App


def test_global_providers_isolated_between_apps():
    a1 = App()
    a2 = App()
    a1.register_global_provider(str, "solo-a1")
    assert str not in a2._global_providers


def test_register_global_provider_is_visible_to_modules():
    from vesper import Injectable, Module, Controller, command
    from vesper.core.module import Container

    @Injectable()
    class FakeService:
        pass

    app = App()
    sentinel = object()
    app.register_global_provider(FakeService, sentinel)

    container = Container([], global_providers=app._global_providers)
    assert container.resolve(FakeService) is sentinel


def test_two_apps_with_same_plugin_dont_share_providers():
    a1 = App()
    a2 = App()
    val1 = object()
    val2 = object()
    a1.register_global_provider(int, val1)
    a2.register_global_provider(int, val2)
    assert a1._global_providers[int] is val1
    assert a2._global_providers[int] is val2
    assert a1._global_providers[int] is not a2._global_providers[int]
