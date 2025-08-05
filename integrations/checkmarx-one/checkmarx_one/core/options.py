from typing import List, NotRequired, Optional, Required, TypedDict


class ListProjectOptions(TypedDict):
    """Options for listing projects."""

    pass


class SingleProjectOptions(TypedDict):
    """Options for fetching a single project."""

    project_id: Required[str]


class ListScanOptions(TypedDict):
    """Options for listing scans."""

    project_ids: NotRequired[Optional[List[str]]]


class SingleScanOptions(TypedDict):
    """Options for fetching a single scan."""

    scan_id: Required[str]


class ListScanResultOptions(TypedDict):
    """Options for listing scan results."""

    scan_id: Required[str]
    severity: NotRequired[Optional[List[str]]]
    state: NotRequired[Optional[List[str]]]
    status: NotRequired[Optional[List[str]]]
    sort: NotRequired[Optional[List[str]]]
    exclude_result_types: NotRequired[Optional[str]]


class SingleScanResultOptions(TypedDict):
    """Options for fetching a single scan result."""

    scan_id: Required[str]
    result_id: Required[str]
