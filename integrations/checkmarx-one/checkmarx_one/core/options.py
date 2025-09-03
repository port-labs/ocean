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


class ListScanResultOptions(TypedDict):
    """Options for listing scan results."""

    type: str
    scan_id: Required[str]
    severity: NotRequired[
        Optional[List[Literal["CRITICAL", "HIGH", "MEDIUM", "LOW", "INFO"]]]
    ]
    state: NotRequired[
        Optional[
            List[
                Literal[
                    "TO_VERIFY",
                    "CONFIRMED",
                    "URGENT",
                    "NOT_EXPLOITABLE",
                    "PROPOSED_NOT_EXPLOITABLE",
                    "FALSE_POSITIVE",
                ]
            ]
        ]
    ]
    status: NotRequired[Optional[List[Literal["NEW", "RECURRENT", "FIXED"]]]]
    exclude_result_types: NotRequired[Optional[Literal["DEV_AND_TEST", "NONE"]]]


class SingleScanResultOptions(TypedDict):
    """Options for fetching a single scan result."""

    type: Literal["sca", "container-security"]
    scan_id: Required[str]
    result_id: Required[str]
