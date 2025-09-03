from typing import List, Literal, NotRequired, Optional, Required, TypedDict


class ListProjectOptions(TypedDict):
    """Options for listing projects."""

    pass


class SingleProjectOptions(TypedDict):
    """Options for fetching a single project."""

    project_id: Required[str]


class ListScanOptions(TypedDict):
    """Options for listing scans."""

    project_names: NotRequired[Optional[List[str]]]
    branches: NotRequired[Optional[List[str]]]
    statuses: NotRequired[
        Optional[
            List[
                Literal[
                    "Queued", "Running", "Completed", "Failed", "Partial", "Canceled"
                ]
            ]
        ]
    ]
    from_date: NotRequired[Optional[str]]


class SingleScanOptions(TypedDict):
    """Options for fetching a single scan."""

    scan_id: Required[str]


class ListApiSecOptions(TypedDict):
    """Options for listing API sec scan results."""

    scan_id: Required[str]


class SingleApiSecOptions(TypedDict):
    """Options for fetching a single API sec scan result."""

    risk_id: Required[str]


class ListSastOptions(TypedDict, total=False):
    """Options for listing SAST scan results."""

    # Required
    scan_id: Required[str]
    visible_columns: NotRequired[Optional[List[str]]]


class SingleSastOptions(TypedDict):
    """Options for fetching a single SAST scan result via filters."""

    scan_id: Required[str]
    result_id: Required[str]
