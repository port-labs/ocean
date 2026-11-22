from enum import IntEnum


class ValidationExitCode(IntEnum):
    PASS = 0
    VALIDATION_FAILED = 1
    SETUP_ERROR = 2


class ValidationSetupError(Exception):
    """Invalid configuration or missing prerequisites before a validation run."""

    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message


class ValidationFailedError(Exception):
    """Scenario execution or comparison failed."""

    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message
