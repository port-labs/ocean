class DuplicateActionExecutorError(Exception):
    """
    Raised when attempting to register an executor for an action that already has an existing executor.
    """

    pass


class RunAlreadyAcknowledgedError(Exception):
    """
    Raised when attempting to acknowledge a run that has already been acknowledged.
    """

    pass


class ActionExecutionError(Exception):
    """
    Raised by integration executors for expected action failures such as invalid
    input or upstream API rejections. The execution manager logs these without a
    stack trace and reports the message directly to Port.

    ``status_label`` is an optional phase description shown on the run in Port,
    letting an executor say which step failed rather than only why. Keep it to
    two words at most, since it is rendered as a label. Subclasses can set
    ``DEFAULT_STATUS_LABEL`` so every raise site gets a meaningful label without
    repeating it.
    """

    DEFAULT_STATUS_LABEL: str | None = None

    def __init__(self, message: str, status_label: str | None = None) -> None:
        super().__init__(message)
        self.status_label = status_label or self.DEFAULT_STATUS_LABEL
