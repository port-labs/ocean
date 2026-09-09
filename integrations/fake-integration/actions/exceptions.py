from port_ocean.exceptions.execution_manager import ActionExecutionError


class MissingExecutionPropertyError(ActionExecutionError):
    """Raised when a required execution property is absent from the action run."""


class TriggerFakeTaskError(ActionExecutionError):
    """Raised when the fake third-party API fails to start a task."""
