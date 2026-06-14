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


class InvalidMessageError(VesperError):
    """
    Exception raised for invalid inter-process communication (IPC) messages.

    This error is used to signify that a received message in an IPC system
    does not conform to the expected format, structure, or protocol. It is
    intended to help identify and handle malformed or unexpected IPC messages
    effectively.
    """
