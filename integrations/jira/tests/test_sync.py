# from typing import Any
# from unittest.mock import AsyncMock

# import pytest
# from port_ocean import Ocean
# from port_ocean.tests.helpers.ocean_app import (
#     get_integation_resource_configs,
#     get_raw_result_on_integration_sync_resource_config,
# )

# from client import JiraClient


# @pytest.mark.asyncio
# async def test_full_sync_produces_correct_response_from_api(
#     monkeypatch: Any,
#     ocean_app: Ocean,
#     integration_path: str,
#     issues: list[dict[str, Any]],
#     projects: list[dict[str, Any]],
#     mock_ocean_context: Any,
# ) -> None:
#     projects_mock = AsyncMock()
#     projects_mock.return_value = projects
#     issues_mock = AsyncMock()
#     issues_mock.return_value = issues

#     monkeypatch.setattr(JiraClient, "get_all_projects", projects_mock)
#     monkeypatch.setattr(JiraClient, "get_all_issues", issues_mock)
#     resource_configs = get_integation_resource_configs(integration_path)
#     for resource_config in resource_configs:
#         print(resource_config)
#         results = await get_raw_result_on_integration_sync_resource_config(
#             ocean_app, resource_config
#         )
#         assert len(results) > 0
#         entities, errors = results
#         assert len(errors) == 0
#         # the factories have 4 entities each
#         # all in one batch
#         assert len(list(entities)) == 1
