import pytest
from vesper.core.module import Container


@pytest.fixture(autouse=True)
def clear_container_globals():
    Container.clear_global()
    yield
    Container.clear_global()
