import pytest
from pydantic.v1 import BaseModel

from integration import (
    CheckmarxOneApiSecSelector,
    CheckmarxOneDastScanResultSelector,
    CheckmarxOneKicsSelector,
    CheckmarxOneResultSelector,
    CheckmarxOneSastSelector,
)


@pytest.mark.parametrize(
    "selector, field, expected_default",
    [
        (CheckmarxOneApiSecSelector, "scan_filter", {"projectIds": [], "since": 90}),
        (
            CheckmarxOneDastScanResultSelector,
            "dast_scan_filter",
            {"since": 90, "maxResults": 3000},
        ),
        (CheckmarxOneDastScanResultSelector, "filter", {}),
        (CheckmarxOneKicsSelector, "scan_filter", {"projectIds": [], "since": 90}),
        (CheckmarxOneResultSelector, "scan_filter", {"projectIds": [], "since": 90}),
        (CheckmarxOneSastSelector, "scan_filter", {"projectIds": [], "since": 90}),
    ],
)
def test_nested_filter_defaults_omit_none_values(
    selector: type[BaseModel], field: str, expected_default: dict[str, object]
) -> None:
    assert selector.schema()["properties"][field]["default"] == expected_default
