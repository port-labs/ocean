from port_ocean.exceptions.execution_manager import ActionExecutionError


class InvalidActionParametersException(ActionExecutionError):
    """Raised when an action's input parameters are missing or invalid."""

    DEFAULT_STATUS_LABEL = "Invalid inputs"
