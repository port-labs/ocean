class UnexpectedApiResponseError(Exception):
    """Raised when the Anthropic API returns a response shape that doesn't match
    what was expected for the request that was made."""


class WebhookSigningSecretNotConfiguredError(Exception):
    """Raised when webhook signature verification is attempted without a
    configured webhook signing secret."""
