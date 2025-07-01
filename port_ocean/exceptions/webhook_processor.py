from port_ocean.exceptions.base import BaseOceanException


class RetryableError(Exception):
    """Base exception class for errors that should trigger a retry."""

    pass


class WebhookProcessingError(BaseOceanException):
    """Base exception for webhook processing errors"""

    pass


class WebhookEventNotSupportedError(WebhookProcessingError):
    pass
