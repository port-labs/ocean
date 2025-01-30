class RetryableError(Exception):
    """Base exception class for errors that should trigger a retry."""

    pass
