import os
from typing import Any
from unittest.mock import AsyncMock

import pytest

from wiz.client import WizClient
import main

INTEGRATION_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), "../"))

FAKE_ISSUE = {
    "id": "ISSUE-1",
    "status": "OPEN",
    "severity": "HIGH",
    "createdAt": "2023-01-01T00:00:00Z",
    "updatedAt": "2023-01-02T00:00:00Z",
    "projects": [{"id": "PROJECT-1", "name": "Test Project"}],
    "sourceRule": {
        "id": "CONTROL-1",
        "name": "Test Control",
        "controlDescription": "Test Description",
    },
}

FAKE_PROJECT = {
    "id": "PROJECT-1",
    "name": "Test Project",
    "businessUnit": "IT",
    "description": "Test Project Description",
}

@pytest.mark.asyncio
async def test_resync_issues(monkeypatch: Any) -> None:
    mock_client = AsyncMock(spec=WizClient)
    mock_client.get_issues.return_value = AsyncMock(return_value=[[FAKE_ISSUE]])

    monkeypatch.setattr(main, "init_client", lambda: mock_client)
    monkeypatch.setattr(main, "event", AsyncMock(resource_config=AsyncMock(selector=AsyncMock(status_list=["OPEN"]))))

    result = [issues async for issues in await main.resync_issues("issue")]

    assert len(result) == 1
    assert len(result[0]) == 1
    assert result[0][0]["id"] == FAKE_ISSUE["id"]

@pytest.mark.asyncio
async def test_resync_projects(monkeypatch: Any) -> None:
    mock_client = AsyncMock(spec=WizClient)
    mock_client.get_projects.return_value = AsyncMock(return_value=[[FAKE_PROJECT]])

    monkeypatch.setattr(main, "init_client", lambda: mock_client)

    result = [projects async for projects in await main.resync_projects("project")]

    assert len(result) == 1
    assert len(result[0]) == 1
    assert result[0][0]["id"] == FAKE_PROJECT["id"]

@pytest.mark.asyncio
async def test_resync_controls(monkeypatch: Any) -> None:
    mock_client = AsyncMock(spec=WizClient)
    mock_client.get_cached_issues.return_value = AsyncMock(return_value=[[FAKE_ISSUE]])

    monkeypatch.setattr(main, "init_client", lambda: mock_client)

    result = [controls async for controls in await main.resync_controls("control")]

    assert len(result) == 1
    assert len(result[0]) == 1
    assert result[0][0]["id"] == FAKE_ISSUE["sourceRule"]["id"]

@pytest.mark.asyncio
async def test_resync_service_tickets(monkeypatch: Any) -> None:
    fake_issue_with_ticket = FAKE_ISSUE.copy()
    fake_issue_with_ticket["serviceTickets"] = [{"externalId": "TICKET-1", "name": "Test Ticket", "url": "http://example.com"}]

    mock_client = AsyncMock(spec=WizClient)
    mock_client.get_cached_issues.return_value = AsyncMock(return_value=[[fake_issue_with_ticket]])

    monkeypatch.setattr(main, "init_client", lambda: mock_client)

    result = [tickets async for tickets in await main.resync_service_tickets("serviceTicket")]

    assert len(result) == 1
    assert len(result[0]) == 1
    assert result[0][0]["externalId"] == "TICKET-1"

@pytest.mark.asyncio
async def test_handle_webhook_request(monkeypatch: Any) -> None:
    mock_client = AsyncMock(spec=WizClient)
    mock_client.get_single_issue.return_value = FAKE_ISSUE

    monkeypatch.setattr(main, "init_client", lambda: mock_client)
    monkeypatch.setattr(main, "ocean", AsyncMock())

    fake_token = AsyncMock()
    fake_token.credentials = "test_token"

    monkeypatch.setattr(main, "ocean", AsyncMock(integration_config={"wiz_webhook_verification_token": "test_token"}))

    result = await main.handle_webhook_request({"issue": {"id": "ISSUE-1"}}, fake_token)

    assert result == {"ok": True}
    main.ocean.register_raw.assert_called_once_with(main.ObjectKind.ISSUE, [FAKE_ISSUE])
