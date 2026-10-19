from port_ocean.exceptions.base import BaseOceanException
from port_ocean.exceptions.core import OceanAbortException


class MissingIntegrationCredentialException(BaseOceanException):
    pass


class BitbucketFileWalkError(OceanAbortException):
    pass


class BitbucketFileReadError(BaseOceanException):
    """One file's content could not be read, where the listing said it exists.

    Constructed and recorded by file_kind, never raised: raising would cancel the other
    content fetches in flight for that page. It reaches the operator inside the
    ExceptionGroup that BitbucketFileWalkError carries once the walk has finished.
    """
