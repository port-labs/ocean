import logging
from typing import Optional, Any, Protocol
from dataclasses import dataclass
import json


@dataclass
class LoggerConfig:
    log_path: str
    log_level: str = "INFO"
    structured: bool = False


class LoggerProtocol(Protocol):
    """
    Defines the public contract for any logger implementation of ours - structured or not
    """

    @classmethod
    def setup(cls, config: LoggerConfig) -> None: ...

    @classmethod
    def log_webhook_event(
        cls,
        *,
        event_type: str,
        data: Optional[Any] = None,
        source: str,
        is_verified: bool,
        message: str = "",
    ) -> None: ...

    @classmethod
    def log_ingestion_stats(
        cls, *, total_records: int, success_count: int, failure_count: int
    ) -> None: ...

    @classmethod
    def log_request_and_response(
        cls,
        *,
        method: str,
        url: str,
        headers: dict,
        body: Optional[Any] = None,
        response_status: int,
        response_body: Optional[Any] = None,
        error: Optional[str] = None,
    ) -> None: ...

    @classmethod
    def log_error(cls, *, error: Exception, context: Optional[str] = None) -> None: ...


class Logger:
    """
    Logging utility for the sailpoint integration system
    """

    LOG_LEVEL_INFO = logging.INFO
    LOG_LEVEL_ERROR = logging.ERROR
    LOG_LEVEL_DEBUG = logging.DEBUG

    SENSITIVE_DATA = (
        "password",
        "secret",
        "token",
        "api_key",
        "Authorization",
        "access_token",
    )

    @classmethod
    def setup(cls, config: LoggerConfig) -> None:
        pass

    @staticmethod
    def _sanitize_data(data: dict[str, Any] | list) -> dict[str, Any]:
        # recursively sanitizes sensitive data from a dictionary or list
        sanitized_data = {}

        if isinstance(data, dict):
            for key, value in data.items():
                if any(
                    sensitive_key in key.lower()
                    for sensitive_key in Logger.SENSITIVE_DATA
                ):
                    sanitized_data[key] = "***REDACTED***"
                elif isinstance(value, dict):
                    sanitized_data[key] = Logger._sanitize_data(value)
                else:
                    # if we get here, just assume its sanitized LOL
                    sanitized_data[key] = value
        elif isinstance(data, list):
            # TODO: handle these later
            pass
        return sanitized_data

    @staticmethod
    def _exception_handler(self, exception: Exception):
        pass
