class CheckmarxAuthenticationError(Exception):
    """Raised when authentication with Checkmarx One fails."""

    pass


class CheckmarxAPIError(Exception):
    """Raised when Checkmarx One API returns an error."""

    pass
