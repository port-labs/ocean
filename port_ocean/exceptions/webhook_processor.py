from port_ocean.exceptions.base import BaseOceanException


class RetryableError(Exception):
    """Base exception class for errors that should trigger a retry."""



class WebhookProcessingError(BaseOceanException):
    """Base exception for webhook processing errors"""



class WebhookEventNotSupportedError(WebhookProcessingError):
    pass
