from __future__ import annotations

import sys
from contextlib import contextmanager
from unittest.mock import MagicMock

import pytest

from vesper.core.module import Container


@pytest.fixture(autouse=True)
def mock_sentry(monkeypatch):
    """Replace sentry_sdk with a mock that records captures without a network."""
    mock_module = MagicMock()

    scope = MagicMock()

    @contextmanager
    def new_scope():
        yield scope

    mock_module.new_scope = new_scope
    mock_module._scope = scope

    monkeypatch.setitem(sys.modules, "sentry_sdk", mock_module)
    return mock_module


@pytest.fixture(autouse=True)
def restore_excepthook():
    previous = sys.excepthook
    yield
    sys.excepthook = previous


@pytest.fixture(autouse=True)
def clear_container_globals():
    Container.clear_global()
    yield
    Container.clear_global()
