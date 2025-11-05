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
