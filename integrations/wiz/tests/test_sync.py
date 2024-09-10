import os
from typing import Any
from unittest.mock import AsyncMock, patch

import pytest
from port_ocean.tests.helpers import get_raw_result_on_integration_sync_kinds

INTEGRATION_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), "../"))

FAKE_CACHED_ISSUES = [
    {"id": "ISSUE-1", "title": "Test Issue 1", "status": "OPEN"},
    {"id": "ISSUE-2", "title": "Test Issue 2", "status": "IN_PROGRESS"},
]

@pytest.mark.asyncio
async def test_get_cached_issues(monkeypatch: Any) -> None:
    # Mock the event.attributes
    mock_event = AsyncMock()
    mock_event.attributes = {"ISSUES": FAKE_CACHED_ISSUES}

    # Patch the event object in the main module
    with patch("main.event", mock_event):
        results = await get_raw_result_on_integration_sync_kinds(INTEGRATION_PATH)

    assert len(results) > 0
    assert "wiz-issue" in results

    issue_results = results["wiz-issue"]

    assert len(issue_results) > 0
    assert len(issue_results[0][0]) == len(FAKE_CACHED_ISSUES)
    assert len(issue_results[0][1]) == 0

    # Verify that the cached issues are returned
    for i, issue in enumerate(issue_results[0][0]):
        assert issue["id"] == FAKE_CACHED_ISSUES[i]["id"]
        assert issue["title"] == FAKE_CACHED_ISSUES[i]["title"]
        assert issue["status"] == FAKE_CACHED_ISSUES[i]["status"]

@pytest.mark.asyncio
async def test_get_cached_issues_empty_cache(monkeypatch: Any) -> None:
    # Mock the event.attributes with an empty cache
    mock_event = AsyncMock()
    mock_event.attributes = {}

    # Patch the event object in the main module
    with patch("main.event", mock_event):
        results = await get_raw_result_on_integration_sync_kinds(INTEGRATION_PATH)

    assert len(results) > 0
    assert "wiz-issue" in results

    issue_results = results["wiz-issue"]

    assert len(issue_results) > 0
    assert len(issue_results[0][0]) == 0
    assert len(issue_results[0][1]) == 0
