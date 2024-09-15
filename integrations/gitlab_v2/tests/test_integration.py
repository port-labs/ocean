# import os
# from typing import Any
# from unittest.mock import AsyncMock
#
# import pytest
#
# from client import GitlabClient
# from port_ocean.tests.helpers import (
#     get_raw_result_on_integration_sync_kinds,
# )
# from pytest_httpx import HTTPXMock
#
# INTEGRATION_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), "../"))
#
# FAKE_PROJECTS: list[dict[str, Any]]  = [
#     {
#         "id": 1,
#         "name": "Test Project",
#         "path_with_namespace": "test-namespace/test-project",
#         "web_url": "https://gitlab.com/test-namespace/test-project",
#         "description": "Project description",
#     }
# ]
#
# FAKE_GROUPS: list[dict[str, Any]] = [
#     {
#         "id": 1,
#         "title": "Test Group",
#         "visibility": "private",
#         "web_url": "https://gitlab.com/test-namespace/test-group",
#         "description": "Group description",
#     }
# ]
#
# FAKE_MERGE_REQUESTS: list[dict[str, Any]] = [
#     {
#         "id": 1,
#         "title": "Test Merge Request",
#         "state": "opened",
#         "web_url": "https://gitlab.com/test-namespace/test-merge-request",
#     }
# ]
#
# FAKE_ISSUES: list[dict[str, Any]] = [
#     {
#         "id": 1,
#         "title": "Test Issue",
#         "web_url": "https://gitlab.com/test-namespace/test-issue",
#         "description": "Issue description",
#         "state": "opened",
#     }
# ]
#
# async def test_all_resync_methods(monkeypatch: pytest.MonkeyPatch) -> None:
#     get_projects_mock = AsyncMock()
#     get_projects_mock.return_value = [FAKE_PROJECTS]
#
#     get_groups_mock = AsyncMock()
#     get_groups_mock.return_value = [FAKE_GROUPS]
#
#     get_issues_mock = AsyncMock()
#     get_issues_mock.return_value = [FAKE_ISSUES]
#
#     get_merge_request_mock = AsyncMock()
#     get_merge_request_mock.return_value = [FAKE_MERGE_REQUESTS]
#
#     monkeypatch.setattr(GitlabClient, "get_projects", get_projects_mock)
#     monkeypatch.setattr(GitlabClient, "get_groups", get_groups_mock)
#     monkeypatch.setattr(GitlabClient, "get_issues", get_issues_mock)
#     monkeypatch.setattr(GitlabClient, "get_merge_request", get_merge_request_mock)
#
#     results = await get_raw_result_on_integration_sync_kinds(INTEGRATION_PATH)
#
#     assert len(results) > 0
#     assert "projects" in results
#     assert "issues" in results
#     assert "merge_request" in results
#     assert "groups" in results
#
#     project_results = results["projects"]
#     issues_results = results["issues"]
#     merge_requests_results = results["merge_requests"]
#     groups_results = results["groups"]
#
#     assert len(project_results) > 0
#     assert len(issues_results) > 0
#     assert len(merge_requests_results) > 0
#     assert len(groups_results) > 0
