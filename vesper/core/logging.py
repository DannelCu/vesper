"""
Namespaced logging for the framework.

Everything Vesper logs goes under the ``vesper`` logger, so an application can
silence or redirect it without touching the root logger and without affecting its
own logging setup.

A library must not configure logging on import — that would hijack the host
application's configuration — so the root ``vesper`` logger only gets a
``NullHandler`` here. ``configure()`` opts in to actual output and is called by
``App`` according to its ``debug`` flag.
"""
from __future__ import annotations

import logging
import sys

ROOT_LOGGER_NAME = "vesper"

_root = logging.getLogger(ROOT_LOGGER_NAME)
_root.addHandler(logging.NullHandler())

_configured = False


def get_logger(name: str | None = None) -> logging.Logger:
    """
    Return a logger under the ``vesper`` namespace.

    Args:
        name: Sub-namespace, typically the module ("ipc", "notify"). ``None``
              returns the root ``vesper`` logger.
    """
    if not name:
        return _root
    return logging.getLogger(f"{ROOT_LOGGER_NAME}.{name}")


def configure(debug: bool = False, *, stream=None, force: bool = False) -> logging.Logger:
    """
    Attach a stream handler to the ``vesper`` logger.

    Args:
        debug:  DEBUG level when true, WARNING otherwise. Warnings and errors are
                worth seeing in production too — this only changes verbosity, never
                whether failures are reported at all.
        stream: Destination, defaulting to stderr so log output never contaminates
                anything the app writes to stdout.
        force:  Reattach even if already configured. Mainly for tests.

    Returns:
        The configured ``vesper`` logger.
    """
    global _configured

    if _configured and not force:
        _root.setLevel(logging.DEBUG if debug else logging.WARNING)
        return _root

    handler = logging.StreamHandler(stream if stream is not None else sys.stderr)
    handler.setFormatter(
        logging.Formatter("[%(levelname)s] %(name)s: %(message)s")
    )

    # Replace rather than append, so repeated configure() calls cannot cause every
    # message to be emitted several times.
    for existing in list(_root.handlers):
        if not isinstance(existing, logging.NullHandler):
            _root.removeHandler(existing)

    _root.addHandler(handler)
    _root.setLevel(logging.DEBUG if debug else logging.WARNING)

    # The app owns its own logging; ours should not also bubble to the root logger.
    _root.propagate = False

    _configured = True
    return _root


def reset() -> None:
    """Undo configure(). Exists so tests can start from a known state."""
    global _configured

    for handler in list(_root.handlers):
        if not isinstance(handler, logging.NullHandler):
            _root.removeHandler(handler)

    _root.setLevel(logging.NOTSET)
    _root.propagate = True
    _configured = False
