class CursorAgentsPaginationError(Exception):
    """Raised when one or more pages could not be fetched after retries.

    Raising (rather than finishing silently) makes Ocean skip its delete phase,
    so the entities behind the skipped pages are preserved until the next resync.
    """
