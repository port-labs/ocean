import os
from typing import Any
from unittest.mock import AsyncMock

import pytest
from port_ocean.tests.helpers.ocean_app import (
    get_integation_resource_configs,
    get_integration_ocean_app,
    get_raw_result_on_integration_sync_resource_config,
)

from client import JiraClient

from .fixtures import ISSUES, PROJECTS

INTEGRATION_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), "../"))


@pytest.mark.asyncio
async def test_full_sync_produces_correct_response_from_api(
    monkeypatch: Any,
) -> None:
    projects_mock = AsyncMock()
    projects_mock.return_value = PROJECTS
    issues_mock = AsyncMock()
    issues_mock.return_value = ISSUES

    monkeypatch.setattr(JiraClient, "get_all_projects", projects_mock)
    monkeypatch.setattr(JiraClient, "get_all_issues", issues_mock)
    config = {
        "event_listener": {"type": "POLLING"},
        "integration": {
            "config": {
                "jira_host": "https://getport.atlassian.net",
                "atlassian_user_email": "jira@atlassian.net",
                "atlassian_user_token": "asdf",
            }
        },
        "port": {
            "client_id": "bla",
            "client_secret": "bla",
        },
    }
    print(config)
    app = get_integration_ocean_app(INTEGRATION_PATH, config)
    resource_configs = get_integation_resource_configs(INTEGRATION_PATH)
    for resource_config in resource_configs:
        print(resource_config)
        results = await get_raw_result_on_integration_sync_resource_config(
            app, resource_config
        )
        assert len(results) > 0
        entities, errors = results
        assert len(errors) == 0
        # the factories have 4 entities each
        # all in one batch
        assert len(list(entities)) == 1
