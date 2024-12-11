# from typing import Any
# from unittest.mock import AsyncMock

# from port_ocean import Ocean
# from port_ocean.context.ocean import ocean
# from starlette.testclient import TestClient

# from client import JiraClient

# from .fixtures import ISSUE_WEBHOOK, PROJECT_WEBHOOK

# ENDPOINT = "/integration/webhook"


# def test_project_creation_event_will_create_project(
#     monkeypatch: Any, ocean_app: Ocean
# ) -> None:
#     client = TestClient(ocean_app)
#     project: dict[str, Any] = {**PROJECT_WEBHOOK, "webhookEvent": "project_created"}
#     get_single_project_mock = AsyncMock()
#     get_single_project_mock.return_value = project["project"]
#     register_raw_mock = AsyncMock()
#     monkeypatch.setattr(JiraClient, "get_single_project", get_single_project_mock)
#     monkeypatch.setattr(ocean, "register_raw", register_raw_mock)

#     response = client.post(ENDPOINT, json=project)

#     assert response.status_code == 200
#     assert response.json() == {"ok": True}
#     assert get_single_project_mock.called
#     assert register_raw_mock.called
#     register_raw_mock.assert_called_once_with("project", [project["project"]])
#     get_single_project_mock.assert_called_once_with(project["project"]["key"])


# def test_project_deletion_event_will_delete_project(
#     monkeypatch: Any, ocean_app: Ocean
# ) -> None:
#     client = TestClient(ocean_app)
#     project = {**PROJECT_WEBHOOK, "webhookEvent": "project_deleted"}
#     unregister_raw_mock = AsyncMock()
#     monkeypatch.setattr(ocean, "unregister_raw", unregister_raw_mock)

#     response = client.post(ENDPOINT, json=project)

#     assert response.status_code == 200
#     assert response.json() == {"ok": True}
#     assert unregister_raw_mock.called
#     unregister_raw_mock.assert_called_once_with("project", [project["project"]])


# def test_issue_creation_event_will_create_issue(
#     monkeypatch: Any, ocean_app: Ocean
# ) -> None:
#     client = TestClient(ocean_app)
#     issue: dict[str, Any] = {**ISSUE_WEBHOOK, "webhookEvent": "jira:issue_created"}
#     get_all_issues_mock = AsyncMock()
#     get_all_issues_mock.__aiter__.return_value = issue["issue"]
#     register_raw_mock = AsyncMock()
#     monkeypatch.setattr(JiraClient, "get_all_issues", get_all_issues_mock)
#     monkeypatch.setattr(ocean, "register_raw", register_raw_mock)

#     response = client.post(ENDPOINT, json=issue)

#     assert response.status_code == 200
#     assert response.json() == {"ok": True}
#     assert get_all_issues_mock.called
#     assert register_raw_mock.called
#     register_raw_mock.assert_called_once_with("issue", [issue["issue"]])
#     get_all_issues_mock.assert_called_once_with(
#         {"jql": f"key = {issue['issue']['key']}", "fields": "*all"}
#     )


# def test_issue_deletion_event_will_delete_issue(
#     monkeypatch: Any, ocean_app: Ocean
# ) -> None:
#     client = TestClient(ocean_app)
#     issue = {**ISSUE_WEBHOOK, "webhookEvent": "jira:issue_deleted"}
#     unregister_raw_mock = AsyncMock()
#     monkeypatch.setattr(ocean, "unregister_raw", unregister_raw_mock)

#     response = client.post(ENDPOINT, json=issue)

#     assert response.status_code == 200
#     assert response.json() == {"ok": True}
#     assert unregister_raw_mock.called
#     unregister_raw_mock.assert_called_once_with("issue", [issue["issue"]])


# def test_issue_update_event_will_update_issue(
#     monkeypatch: Any, ocean_app: Ocean
# ) -> None:
#     client = TestClient(ocean_app)
#     issue: dict[str, Any] = {**ISSUE_WEBHOOK, "webhookEvent": "jira:issue_updated"}
#     get_single_issue_mock = AsyncMock()
#     get_single_issue_mock.return_value = issue["issue"]
#     register_raw_mock = AsyncMock()

#     monkeypatch.setattr(JiraClient, "get_single_issue", get_single_issue_mock)
#     monkeypatch.setattr(ocean, "register_raw", register_raw_mock)

#     response = client.post(ENDPOINT, json=issue)

#     assert response.status_code == 200
#     assert response.json() == {"ok": True}
#     assert get_single_issue_mock.called
#     assert register_raw_mock.called
#     register_raw_mock.assert_called_once_with("issue", [issue["issue"]])
#     get_single_issue_mock.assert_called_once_with(
#         {"jql": f"key = {issue['issue']['key']}", "fields": "*all"}
#     )
