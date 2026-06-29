"""Test fixtures for vesper-mongodb.

All tests use a mongomock MongoClient so no real MongoDB instance is needed.
"""
from __future__ import annotations

import pytest

pytest.importorskip("mongomock", reason="mongomock not installed — run: pip install mongomock")

import mongomock
from unittest.mock import patch
from vesper.core.module import Container


@pytest.fixture(autouse=True)
def mock_mongo(monkeypatch):
    """Replace pymongo.MongoClient with mongomock for every test."""
    with patch("pymongo.MongoClient", mongomock.MongoClient):
        yield


@pytest.fixture(autouse=True)
def clear_container_globals():
    Container.clear_global()
    yield
    Container.clear_global()
