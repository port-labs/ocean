from typing import Any, Dict, Optional, TypedDict

from integration import ApiPathParameter


class FetchResourceOptions(TypedDict):
    """Options for exporting data from an HTTP endpoint."""

    kind: str
    method: str
    query_params: Dict[str, Any]
    headers: Dict[str, str]
    body: Optional[Dict[str, Any]]
    data_path: str
    path_parameters: Optional[Dict[str, ApiPathParameter]]
