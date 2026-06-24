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


