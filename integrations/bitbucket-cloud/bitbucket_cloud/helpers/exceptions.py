from port_ocean.exceptions.base import BaseOceanException
from port_ocean.exceptions.core import OceanAbortException


class MissingIntegrationCredentialException(BaseOceanException):
    pass


class BitbucketFileWalkError(OceanAbortException):
    """A file the walk proved exists could not be read.

    Subclasses OceanAbortException so the kind ends in error and reconciliation skips
    its delete phase. Omitting the file instead would let a successful resync delete
    the entity the listing had just confirmed.
    """
