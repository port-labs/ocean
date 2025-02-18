from port_ocean.exceptions.core import OceanAbortException


class GotFeedCreatedSuccessfullyMessageError(Exception):
    pass


class AssetHasNoProjectAncestorError(OceanAbortException):
    pass


class ResourceNotFoundError(Exception):
    pass


class NoProjectsFoundError(ResourceNotFoundError, OceanAbortException):
    pass
