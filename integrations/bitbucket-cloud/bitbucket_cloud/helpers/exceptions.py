from port_ocean.exceptions.base import BaseOceanException
from port_ocean.exceptions.core import OceanAbortException


class MissingIntegrationCredentialException(BaseOceanException):
    pass


class BitbucketFileWalkError(OceanAbortException):
    pass


class BitbucketFileReadError(BaseOceanException):
    """One file's content could not be read.

    Caught in file_kind._collect_walk_failures, which records it and lets the walk
    finish. It is deliberately not an OceanAbortException: the walk decides whether a
    failed read ends the kind, and raises BitbucketFileWalkError when it does.
    """
