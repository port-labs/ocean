from enum import StrEnum
from typing import NamedTuple, Optional

from port_ocean.version import __integration_version__


class ObjectKind(StrEnum):
    PROJECT = "mend-project"
    SECURITY_FINDING = "sca-finding"


class IgnoredError(NamedTuple):
    status: int | str
    message: Optional[str] = None
    type: Optional[str] = None


# Mend attributes API traffic to the calling integration via these headers
# Sent on every request to Mend, including the login calls.
INTEGRATION_AGENT_HEADERS: dict[str, str] = {
    "agent-name": "pi-port",
    "agent-version": __integration_version__ or "unknown",
}
