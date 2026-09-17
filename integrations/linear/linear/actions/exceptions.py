from port_ocean.exceptions.execution_manager import ActionExecutionError


class MissingExecutionPropertyError(ActionExecutionError):
    """Raised when a required execution property is absent from the action run."""

    DEFAULT_STATUS_LABEL = "Invalid inputs"


class LinearActionError(ActionExecutionError):
    """Raised at the action boundary when a Linear operation fails."""

    DEFAULT_STATUS_LABEL = "Linear failed"
