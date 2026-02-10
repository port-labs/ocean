from typing import TypedDict

from integration import HttpServerSelector


class FetchResourceOptions(TypedDict):
    """Options for exporting data from an HTTP endpoint."""

    kind: str
    selector: HttpServerSelector
