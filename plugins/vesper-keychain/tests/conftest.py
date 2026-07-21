import pytest

# Skip this plugin's tests instead of failing collection when the plugin is not
# installed. pytest's testpaths include plugins/, so a bare `pytest` from a fresh
# clone would otherwise abort the entire run — core tests included — on an import
# error here.
keyring = pytest.importorskip(
    "keyring",
    reason="vesper-keychain not installed — run: pip install -e plugins/vesper-keychain",
)
import keyring.backend
from vesper.core.module import Container


class _MemoryKeyring(keyring.backend.KeyringBackend):
    """In-memory keyring backend for tests — never touches the OS keychain."""
    priority = 100

    def __init__(self):
        self._store: dict[tuple[str, str], str] = {}

    def get_password(self, service, username):
        return self._store.get((service, username))

    def set_password(self, service, username, password):
        self._store[(service, username)] = password

    def delete_password(self, service, username):
        import keyring.errors
        if (service, username) not in self._store:
            raise keyring.errors.PasswordDeleteError(username)
        del self._store[(service, username)]


@pytest.fixture(autouse=True)
def memory_keyring():
    """Replace the system keychain with an in-memory backend for each test."""
    original = keyring.get_keyring()
    backend = _MemoryKeyring()
    keyring.set_keyring(backend)
    yield backend
    keyring.set_keyring(original)


@pytest.fixture(autouse=True)
def clear_container_globals():
    Container.clear_global()
    yield
    Container.clear_global()
