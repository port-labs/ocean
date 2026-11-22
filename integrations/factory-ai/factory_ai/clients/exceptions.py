class FactoryAIError(Exception):
    """Base exception for Factory.ai client errors."""


class FactoryAIPaginationError(FactoryAIError):
    """Raised when pagination stops early after a request failure."""
