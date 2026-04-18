"""Project error hierarchy."""


class MetiscodeError(Exception):
    """Base error for all metiscode exceptions."""


class AuthError(MetiscodeError):
    """Raised when provider credentials are missing."""


class PermissionDeniedError(MetiscodeError):
    """Raised when runtime permission evaluation blocks an action."""

