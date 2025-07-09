class AWSSessionError(Exception):
    """Raised when an AWS session or assume role operation fails."""


class CredentialsProviderError(Exception):
    """Raised when there is a credentials provider or assume role error."""


class ResyncStrategyError(Exception):
    """Raised when there is an error creating a resync strategy."""
