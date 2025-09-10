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


class ListKicsOptions(TypedDict):
    """Options for listing KICS scan results (IaC Security)."""

    scan_id: Required[str]
    severity: NotRequired[
        Optional[List[Literal["CRITICAL", "HIGH", "MEDIUM", "LOW", "INFO"]]]
    ]
    status: NotRequired[Optional[List[Literal["NEW", "RECURRENT", "FIXED"]]]]


class ListSastOptions(TypedDict, total=False):
    """Options for listing SAST scan results."""

    scan_id: Required[str]
    compliance: NotRequired[Optional[str]]
    group: NotRequired[Optional[str]]
    include_nodes: NotRequired[bool]
    language: NotRequired[Optional[List[str]]]
    result_id: NotRequired[Optional[str]]
    severity: NotRequired[
        Optional[List[Literal["critical", "high", "medium", "low", "info"]]]
    ]
    status: NotRequired[Optional[List[Literal["new", "recurrent", "fixed"]]]]
    category: NotRequired[Optional[str]]
    state: NotRequired[
        Optional[
            List[
                Literal[
                    "to_verify",
                    "not_exploitable",
                    "proposed_not_exploitable",
                    "confirmed",
                    "urgent",
                ]
            ]
        ]
    ]
    visible_columns: NotRequired[Optional[List[str]]]


class SingleSastOptions(TypedDict):
    """Options for fetching a single SAST scan result via filters."""

    scan_id: Required[str]
    result_id: Required[str]
    include_nodes: NotRequired[Optional[bool]]
    visible_columns: NotRequired[Optional[List[str]]]
