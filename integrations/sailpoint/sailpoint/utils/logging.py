import logging
from typing import Optional, Any, Protocol
from dataclasses import dataclass
from fastapi.requests import Request
import json
import os
from pathlib import Path

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

    @staticmethod
    def _send_to_logger(origin: str, request: Request, response: Any) -> None: ...


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
    def _exception_handler(exc: Exception):
        pass
