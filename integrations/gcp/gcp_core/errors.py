from port_ocean.exceptions.core import OceanAbortException


class GotFeedCreatedSuccessfullyMessageError(OceanAbortException):
    pass


class AssetHasNoProjectAncestorError(OceanAbortException):
    pass


class ResourceNotFoundError(Exception):
    pass
