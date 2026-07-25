class VesperError(Exception):
    """
    Base exception for all Vesper errors.
    """


class CommandNotFoundError(VesperError):
    """
    Raised when a command does not exist.
    """


class CommandAlreadyRegisteredError(VesperError):
    """
    Raised when attempting to register
    an existing command.
    """


class ForbiddenError(VesperError):
    """
    Raised when a guard rejects a command call.
    """


class MissingProviderError(VesperError):
    """
    Raised when the DI container is asked to resolve a type that is neither
    registered as a provider (global or per-App) nor marked @Injectable()/
    @Controller().

    Without this, Container.resolve() could not tell "no provider registered"
    apart from "this type happens to have a zero-argument constructor" — it
    would silently build an empty instance instead, which then fails
    confusingly wherever the caller actually uses it. See docs/module-system.md.
    """


