# from typing import Any
# from unittest.mock import AsyncMock

# from port_ocean import Ocean
# from port_ocean.tests.helpers.ocean_app import (
#     get_integation_resource_configs,
#     get_raw_result_on_integration_sync_resource_config,
# )

# from client import SonarQubeClient


# async def test_full_sync_produces_correct_response_from_api(
#     monkeypatch: Any,
#     ocean_app: Ocean,
#     integration_path: str,
#     issues: list[dict[str, Any]],
#     projects: list[dict[str, Any]],
#     component_projects: list[dict[str, Any]],
#     analysis: list[dict[str, Any]],
#     portfolios: list[dict[str, Any]],
# ) -> None:
#     projects_mock = AsyncMock()
#     projects_mock.return_value = projects
#     component_projects_mock = AsyncMock()
#     component_projects_mock.return_value = component_projects
#     issues_mock = AsyncMock()
#     issues_mock.return_value = issues
#     saas_analysis_mock = AsyncMock()
#     saas_analysis_mock.return_value = analysis
#     on_onprem_analysis_resync_mock = AsyncMock()
#     on_onprem_analysis_resync_mock.return_value = analysis
#     on_portfolio_resync_mock = AsyncMock()
#     on_portfolio_resync_mock.return_value = portfolios

#     monkeypatch.setattr(SonarQubeClient, "get_projects", projects_mock)
#     monkeypatch.setattr(SonarQubeClient, "get_components", component_projects_mock)
#     monkeypatch.setattr(SonarQubeClient, "get_all_issues", issues_mock)
#     monkeypatch.setattr(
#         SonarQubeClient, "get_all_sonarcloud_analyses", saas_analysis_mock
#     )
#     monkeypatch.setattr(
#         SonarQubeClient, "get_all_sonarqube_analyses", on_onprem_analysis_resync_mock
#     )
#     monkeypatch.setattr(SonarQubeClient, "get_all_portfolios", on_portfolio_resync_mock)
#     resource_configs = get_integation_resource_configs(integration_path)
#     for resource_config in resource_configs:
#         print(resource_config)
#         results = await get_raw_result_on_integration_sync_resource_config(
#             ocean_app, resource_config
#         )
#         assert len(results) > 0
#         entities, errors = results
#         assert len(errors) == 0
#         # the factories have several entities each
#         # all in one batch
#         assert len(list(entities)) == 1
