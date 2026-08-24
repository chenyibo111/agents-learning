"""Common errors raised by the lesson 07 framework."""


class FrameworkError(RuntimeError):
    """Base error for the Mini Agent Framework."""


class InvalidActionError(FrameworkError):
    """Raised when a model action violates the internal contract."""


class ToolNotFoundError(FrameworkError):
    """Raised when a model requests an unregistered tool."""


class ToolValidationError(FrameworkError):
    """Raised when tool arguments do not match the declared schema."""


class PermissionDeniedError(FrameworkError):
    """Raised when the current run lacks a tool permission."""


class RetryableToolError(FrameworkError):
    """A tool failure that may succeed when called again."""


class ToolExecutionError(FrameworkError):
    """A non-retryable tool execution failure."""
