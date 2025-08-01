class IgnoredErrors(Exception):
    """
    A custom exception for HTTP errors that should be ignored,
    such as 401, 403, and 404, when a resource might not exist or be
    accessible.
    """

    #!todo: add more specific exceptions for each resource

    pass


class ResourceNotFoundError(Exception):
    pass
