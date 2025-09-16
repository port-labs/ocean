import logging
from typing import Callable, Optional, Any, Protocol
from dataclasses import dataclass
from fastapi.requests import Request
from datetime import datetime
import json
import os
from pathlib import Path
from functools import wraps
from fastapi.responses import Response
import httpx

from sailpoint.exceptions import ThirdPartyAPIError, is_success

BASE_DIR = Path(__file__).resolve().parent.parent
os.makedirs(os.path.join(BASE_DIR, "logs"), exist_ok=True)
LOG_FILE_PATH = os.path.join(BASE_DIR, "logs", "sailpoint_integration.log")


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
    def setup(cls, config: LoggerConfig, log_to_tty: bool = False) -> None: ...

    @classmethod
    def log_webhook_receipt(
        cls,
        *,
        event_type: str,
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
    def log_error(
        cls, *, message: str, error: Exception, context: Optional[dict | str] = None
    ) -> None: ...

    @staticmethod
    def _send_to_logger(origin: str, request: Request, response: Any) -> None: ...

    @staticmethod
    def log_external_api_call(
        func: Any,
    ) -> Any: ...

    @classmethod
    def log_retry_decision(
        cls,
        *,
        attempt: int,
        max_attempts: int,
        backoff_ms: int,
        reason: str,
    ) -> None: ...


class StructuredLogFormatter(logging.Formatter):
    """
    Custom log formatter to output logs in structured JSON format
    """

    # This kind of logs, can be easily parsed by log management systems e.g
    # Splunk, ELK stack, Datadog, etc. Let's face it, unstructured logs are a pain to work with
    # when you have to search for specific events or patterns.
    #
    # That said, you might find it had to read raw logs in JSON format ...:sweat_smile: LOL

    def format(self, record: logging.LogRecord) -> str:
        log_record = {
            "timestamp": self.formatTime(record, self.datefmt),
            "level": record.levelname,
            "message": record.getMessage(),
            "origin": getattr(record, "origin", "unknown"),
        }

        if hasattr(record, "extra"):
            log_record.update(record.extra)  # type: ignore

        if isinstance(record.args, dict):
            # additionally include any extra fields passed in the log call
            log_record.update(record.args)

        if record.exc_info:
            log_record["exception"] = self.formatException(record.exc_info)

        return json.dumps(log_record)


class Logger:
    """
    Logging utility for the sailpoint integration system
    """

    LOG_LEVEL_INFO = logging.INFO
    LOG_LEVEL_ERROR = logging.ERROR
    LOG_LEVEL_DEBUG = logging.DEBUG
    LOG_LEVEL_WARNING = logging.WARNING

    SENSITIVE_DATA = (
        "password",
        "secret",
        "token",
        "api_key",
        "Authorization",
        "access_token",
    )

    _logger: Optional[logging.Logger] = None

    @classmethod
    def setup(cls, config: LoggerConfig, log_to_tty: bool = False) -> None:
        if cls._logger:
            return

        cls._logger = logging.getLogger("sailpoint_integration_logger")

        file_handler = logging.FileHandler(config.log_path)
        if config.structured:
            formatter = StructuredLogFormatter()
            file_handler.setFormatter(formatter)

        cls._logger.addHandler(file_handler)

        if log_to_tty:
            console_handler = logging.StreamHandler()
            if config.structured:
                formatter = StructuredLogFormatter()
                console_handler.setFormatter(formatter)
            else:
                console_formatter = logging.Formatter(
                    "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
                )
                console_handler.setFormatter(console_formatter)
            cls._logger.addHandler(console_handler)

        log_level = getattr(logging, config.log_level.upper(), logging.INFO)
        cls._logger.setLevel(log_level)

        cls._logger.info("Logger is all setup and ready to go!")

    @classmethod
    def _get_logger(cls) -> logging.Logger:
        """Returns an instance of the logger, or raises an error if not initialized"""
        if not cls._logger:
            raise RuntimeError("Logger not initialized. Call `Logger.setup()` first")
        return cls._logger

    @staticmethod
    def _sanitize_data(data: Any) -> dict[str, Any]:
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
        else:
            sanitized_data = data
        return sanitized_data

    @staticmethod
    def _exception_handler(exc: Exception, /, *args: Any, **kwargs: Any) -> None:
        logger = Logger._get_logger()
        log_data = {
            "error_type": type(exc).__name__,
            "error_message": str(exc),
            "args": args,
            "kwargs": Logger._sanitize_data(kwargs),
        }
        logger.error(
            "Exception caught", extra={"origin": "exception_handler", "extra": log_data}
        )

    @staticmethod
    def log_external_api_call(
        func: Any,
    ) -> Any:
        """Log external api calls to third party."""

        @wraps(func)
        def inner_wrapper(*args: tuple[Any, ...], **kwargs: dict[str, Any]) -> Any:
            logger = Logger._get_logger()

            origin = f"ThirdPartyConnection::{args[0].third_party}"  # type: ignore

            request_payload: dict[str, Any] = {
                "method": kwargs.get("method"),
                "url": kwargs.get("url"),
            }
            if "params" in kwargs:
                request_payload["params"] = Logger._sanitize_data(kwargs.get("params"))
            if "post_data" in kwargs:
                request_payload["post_data"] = Logger._sanitize_data(
                    kwargs.get("post_data")
                )
            data = {
                "timestamp": datetime.timestamp(datetime.now()),
                "origin": origin,
                "request_context": request_payload,
            }

            try:
                response = func(*args, **kwargs)

                data["response_context"] = {
                    "payload": Logger._sanitize_data(response.response_data),
                    "status_code": response.status_code,
                }

                if is_success(response.status_code):
                    data["log_level"] = Logger.LOG_LEVEL_INFO
                    logger.info(origin, extra=data)
                else:
                    data["log_level"] = Logger.LOG_LEVEL_WARNING
                    logger.warning(origin, extra=data)

                return response
            except ThirdPartyAPIError as api_error:
                data["log_level"] = Logger.LOG_LEVEL_WARNING
                data["response_context"] = {
                    "payload": api_error.response_data,
                    "status_code": api_error.response_code,
                }
                logger.warning(origin, extra=data)
                raise api_error

        return inner_wrapper

    @classmethod
    def log_webhook_receipt(
        cls,
        *,
        event_type: str,
        source: str,
        is_verified: bool,
        message: str = "",
    ):
        logger = cls._get_logger()
        logger.info(
            "Webhook Received",
            {
                "event_type": event_type,
                "source": source,
                "is_verified": is_verified,
                "message": message,
            },
            extra={"origin": "webhook_receipt"},
        )

    @classmethod
    def log_retry_decision(
        cls,
        *,
        attempt: int,
        max_attempts: int,
        backoff_ms: int,
        reason: str,
    ):
        """
        Logs a decision to retry an operation, including backoff details.
        """
        logger = cls._get_logger()
        logger.info(
            "Retry Decision",
            {
                "attempt": attempt,
                "max_attempts": max_attempts,
                "backoff_ms": backoff_ms,
                "reason": reason,
            },
            extra={"origin": "retry_decision"},
        )

    @classmethod
    def log_error(
        cls,
        *,
        message: str,
        error: Optional[Exception] = None,
        context: Optional[dict | str] = None,
    ):
        logger = cls._get_logger()

        log_data = {
            "error_type": type(error).__name__,
            "error_message": str(error),
            "timestamp": datetime.timestamp(datetime.now()),
        }

        if context:
            log_data["context"] = Logger._sanitize_data(context)

        if error:
            logger.error(message, exc_info=True)
        else:
            logger.error(message, extra={"origin": "error_logger", "extra": log_data})

    @classmethod
    async def log_request_and_response(
        cls,
        *,
        origin: str,
    ) -> Callable:
        @wraps
        async def wrapper(func: Callable) -> Callable:
            @wraps(func)
            async def inner_wrapper(self, *args: Any, **kwargs: Any) -> Any:
                try:
                    response = await func(self, *args, **kwargs)
                    await Logger._send_to_logger(
                        origin=origin,
                        method=kwargs.get("method", "UNKNOWN"),
                        url=kwargs.get("url", ""),
                        headers=kwargs.get("headers", {}),
                        request_body=kwargs.get("data") or kwargs.get("json"),
                        response=response if hasattr(response, "status_code") else None,
                        latency=getattr(response, "latency", None),
                    )
                    return response
                except Exception as exc:
                    Logger._exception_handler(exc, origin=origin, **kwargs)
                    raise exc

            return inner_wrapper

        return wrapper

    @staticmethod
    async def _send_to_logger(
        origin: str,
        method: str,
        url: str,
        headers: dict[str, Any],
        request_body: Any,
        response: Optional["httpx.Response"] = None,
        latency: Optional[float] = None,
    ) -> None:
        logger = Logger._get_logger()
        log_data: dict[str, Any] = {
            "origin": origin,
            "request_context": {
                "method": method,
                "url": url,
                "headers": Logger._sanitize_data(headers),
                "body": Logger._sanitize_data(request_body),
            },
        }

        if latency:
            log_data["latency_ms"] = latency

        if response is not None:
            log_data["response_context"] = {
                "status_code": response.status_code,
                "payload": Logger._sanitize_data(await response.aread()),
            }

        logger.info("External API call", extra={"extra": log_data})
