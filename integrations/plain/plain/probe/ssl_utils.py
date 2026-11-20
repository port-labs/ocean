"""SSL/TLS error detection utilities for Plain probe."""

import ssl


def is_ssl_error(error: Exception) -> bool:
    """Check if an exception is an SSL/TLS certificate error.

    Walks the exception chain (__cause__ and __context__) to detect
    ssl.SSLError or ssl.SSLCertVerificationError, which indicate
    certificate validation failures or TLS handshake problems.

    These are not transient and should not be retried.

    Args:
        error: The exception to inspect.

    Returns:
        True if the error or any error in its chain is an SSL error.
    """
    current: Exception | None = error
    seen = set()
    while current is not None:
        if id(current) in seen:
            break
        seen.add(id(current))
        if isinstance(current, (ssl.SSLError, ssl.SSLCertVerificationError)):
            return True
        # Check both __cause__ (explicit) and __context__ (implicit)
        next_error = getattr(current, "__cause__", None)
        if next_error is None:
            next_error = getattr(current, "__context__", None)
        current = next_error
    return False
