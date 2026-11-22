from enum import IntEnum


class ValidationExitCode(IntEnum):
    PASS = 0
    VALIDATION_FAILED = 1
    SETUP_ERROR = 2


class ValidationCliError(Exception):
    """Base for CLI-facing validation errors with a prefix and exit code."""

    exit_code: ValidationExitCode
    prefix: str

    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message


class ValidationSetupError(ValidationCliError):
    """Invalid configuration or missing prerequisites before a validation run."""

    exit_code = ValidationExitCode.SETUP_ERROR
    prefix = "Setup error"


class ValidationFailedError(ValidationCliError):
    """Scenario execution or comparison failed."""

    exit_code = ValidationExitCode.VALIDATION_FAILED
    prefix = "Validation failed"
