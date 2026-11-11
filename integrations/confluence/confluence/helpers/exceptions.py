class ConfluenceError(Exception):
    """Base error for the Confluence integration."""


class ConfluenceAuthenticationError(ConfluenceError):
    """Raised when Confluence rejects the Atlassian email or API token."""


class MissingConfluencePermissionError(ConfluenceError):
    """Raised when the Atlassian account cannot view the requested content."""


class ConfluenceApiError(ConfluenceError):
    """Raised when a Confluence response cannot be used safely."""
