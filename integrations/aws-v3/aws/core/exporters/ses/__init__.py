# mypy: implicit_reexport
from aws.core.exporters.ses.email_identity.exporter import SesEmailIdentityExporter
from aws.core.exporters.ses.email_identity.models import (
    SingleEmailIdentityRequest,
    PaginatedEmailIdentityRequest,
)
