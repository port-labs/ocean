from port_ocean.exceptions.base import BaseOceanException


class RetryableError(Exception):
    """Base exception class for errors that should trigger a retry."""

    pass


class WebhookProcessingError(BaseOceanException):
    """Base exception for webhook processing errors"""

    pass


class WebhookEventNotSupportedError(WebhookProcessingError):
    pass


class DeadLetterableError(Exception):
    """Marker for exceptions that should send the originating event to the DLQ."""

    pass


class RateLimitError(DeadLetterableError):
    """Raised when an upstream rate limit prevents processing within the live-event budget."""

    pass
