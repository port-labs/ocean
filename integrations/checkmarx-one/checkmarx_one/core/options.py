from typing import List, NotRequired, Optional, Required, TypedDict


class ListProjectOptions(TypedDict):
    """Options for listing projects."""

    limit: NotRequired[Optional[int]]
    offset: NotRequired[Optional[int]]


class SingleProjectOptions(TypedDict):
    """Options for fetching a single project."""

    project_id: Required[str]


class ListScanOptions(TypedDict):
    """Options for listing scans."""

    project_ids: NotRequired[Optional[List[str]]]
    limit: NotRequired[Optional[int]]
    offset: NotRequired[Optional[int]]


class SingleScanOptions(TypedDict):
    """Options for fetching a single scan."""

    scan_id: Required[str]
