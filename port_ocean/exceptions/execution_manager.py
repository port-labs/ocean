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


class PartitionKeyNotFoundError(Exception):
    """
    Raised when attempting to extract a partition key that is not found in the invocation payload.
    """

    pass


class ActionExecutionError(Exception):
    """
    Raised by integration executors for expected action failures such as invalid
    input or upstream API rejections. The execution manager logs these without a
    stack trace and reports the message directly to Port.
    """

    pass
