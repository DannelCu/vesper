import pytest

# See the note in vesper-keychain's conftest: a missing plugin dependency must skip
# this directory, not abort collection for the whole repository.
pytest.importorskip(
    "sqlalchemy",
    reason="vesper-db not installed — run: pip install -e plugins/vesper-db",
)

from vesper.core.module import Container


@pytest.fixture(autouse=True)
def clear_container_globals():
    Container.clear_global()
    yield
    Container.clear_global()
