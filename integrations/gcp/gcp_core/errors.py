from port_ocean.exceptions.core import OceanAbortError


class GotFeedCreatedSuccessfullyMessageError(Exception):
    pass


class AssetHasNoProjectAncestorError(OceanAbortError):
    pass


class ResourceNotFoundError(Exception):
    pass


class NoProjectsFoundError(ResourceNotFoundError, OceanAbortError):
    pass
