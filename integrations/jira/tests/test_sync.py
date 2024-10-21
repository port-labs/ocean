import os
from typing import Any
from unittest.mock import AsyncMock

from port_ocean.tests.helpers.ocean_app import (
    get_raw_result_on_integration_sync_resource_config,
    get_integration_ocean_app,
    get_integation_resource_configs
)

from client import JiraClient
from .fixtures import PROJECTS, ISSUES

INTEGRATION_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), "../"))

async def test_full_sync_using_mocked_3rd_party(
    monkeypatch: Any,
) -> None:
    projects_mock = AsyncMock()
    projects_mock.return_value = PROJECTS
    issues_mock = AsyncMock()
    issues_mock.return_value = ISSUES

    monkeypatch.setattr(JiraClient, "get_all_projects", projects_mock)
    monkeypatch.setattr(JiraClient, "get_all_issues", issues_mock)

    app = get_integration_ocean_app(INTEGRATION_PATH, {
        "jira_host": "random@atlassian.net",
        "atlassian_user_email": "random@mail.com",
        "atlassian_user_token": "random-super-token"
    })
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
        assert len(list(entities)) ==  1
