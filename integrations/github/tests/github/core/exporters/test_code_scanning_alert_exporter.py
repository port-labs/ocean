from typing import Any, AsyncGenerator
import pytest
from unittest.mock import AsyncMock, patch, MagicMock
import httpx
from github.core.exporters.code_scanning_alert_exporter import (
    RestCodeScanningAlertExporter,
)
from integration import GithubPortAppConfig
from port_ocean.context.event import event_context
from github.core.options import (
    SingleCodeScanningAlertOptions,
    ListCodeScanningAlertOptions,
)
from github.clients.http.rest_client import GithubRestClient


TEST_CODE_SCANNING_ALERTS = [
    {
        "number": 42,
        "created_at": "2020-06-19T11:21:34Z",
        "updated_at": "2020-06-19T11:21:34Z",
        "url": "https://api.github.com/repos/test-org/test-repo/code-scanning/alerts/42",
        "html_url": "https://github.com/test-org/test-repo/security/code-scanning/42",
        "state": "open",
        "fixed_at": None,
        "dismissed_at": None,
        "dismissed_by": None,
        "dismissed_reason": None,
        "dismissed_comment": None,
        "rule": {
            "id": "js/unused-local-variable",
            "name": "Unused variable, import, function or class",
            "severity": "note",
            "security_severity_level": None,
            "description": "Unused variables, imports, functions or classes may be a symptom of a bug and should be examined carefully.",
            "full_description": "Unused variables, imports, functions or classes may be a symptom of a bug and should be examined carefully.",
            "tags": ["maintainability", "useless-code"],
        },
        "tool": {"name": "CodeQL", "guid": None, "version": "2.4.0"},
        "most_recent_instance": {
            "ref": "refs/heads/main",
            "analysis_key": ".github/workflows/codeql-analysis.yml:analyze",
            "environment": "{}",
            "category": ".github/workflows/codeql-analysis.yml:analyze/language:javascript",
            "state": "open",
            "commit_sha": "47b6f9f4e8f7d7c8c1c4d5c6c7d8e9f0a1b2c3d4",
            "message": {"text": "Unused variable index."},
            "location": {
                "path": "lib/index.js",
                "start_line": 2,
                "end_line": 2,
                "start_column": 7,
                "end_column": 12,
            },
            "classifications": [],
        },
    },
    {
        "number": 43,
        "created_at": "2020-06-19T11:21:34Z",
        "updated_at": "2020-06-19T11:21:34Z",
        "url": "https://api.github.com/repos/test-org/test-repo/code-scanning/alerts/43",
        "html_url": "https://github.com/test-org/test-repo/security/code-scanning/43",
        "state": "dismissed",
        "fixed_at": None,
        "dismissed_at": "2020-06-19T11:21:34Z",
        "dismissed_by": {
            "login": "test-user",
            "id": 1,
            "node_id": "MDQ6VXNlcjE=",
            "avatar_url": "https://github.com/images/error/test-user_happy.gif",
            "gravatar_id": "",
            "url": "https://api.github.com/users/test-user",
            "html_url": "https://github.com/test-user",
            "type": "User",
            "site_admin": False,
        },
        "dismissed_reason": "used_in_tests",
        "dismissed_comment": "This variable is used in our tests",
        "rule": {
            "id": "js/unused-local-variable",
            "name": "Unused variable, import, function or class",
            "severity": "warning",
            "security_severity_level": None,
            "description": "Unused variables, imports, functions or classes may be a symptom of a bug and should be examined carefully.",
            "full_description": "Unused variables, imports, functions or classes may be a symptom of a bug and should be examined carefully.",
            "tags": ["maintainability", "useless-code"],
        },
        "tool": {"name": "CodeQL", "guid": None, "version": "2.4.0"},
        "most_recent_instance": {
            "ref": "refs/heads/main",
            "analysis_key": ".github/workflows/codeql-analysis.yml:analyze",
            "environment": "{}",
            "category": ".github/workflows/codeql-analysis.yml:analyze/language:javascript",
            "state": "dismissed",
            "commit_sha": "47b6f9f4e8f7d7c8c1c4d5c6c7d8e9f0a1b2c3d4",
            "message": {"text": "Unused variable temp."},
            "location": {
                "path": "lib/helper.js",
                "start_line": 5,
                "end_line": 5,
                "start_column": 10,
                "end_column": 14,
            },
            "classifications": [],
        },
    },
]


@pytest.mark.asyncio
class TestRestCodeScanningAlertExporter:
    async def test_get_resource(self, rest_client: GithubRestClient) -> None:
        # Create a mock response
        mock_response = MagicMock(spec=httpx.Response)
        mock_response.status_code = 200
        mock_response.json.return_value = TEST_CODE_SCANNING_ALERTS[0]

        exporter = RestCodeScanningAlertExporter(rest_client)

        with patch.object(
            rest_client, "send_api_request", new_callable=AsyncMock
        ) as mock_request:
            mock_request.return_value = TEST_CODE_SCANNING_ALERTS[0].copy()
            alert = await exporter.get_resource(
                SingleCodeScanningAlertOptions(repo_name="test-repo", alert_number="42")
            )

            # Verify the __repository field was added
            expected_alert = {
                **TEST_CODE_SCANNING_ALERTS[0],
                "__repository": "test-repo",
            }
            assert alert == expected_alert

            mock_request.assert_called_once_with(
                f"{rest_client.base_url}/repos/{rest_client.organization}/test-repo/code-scanning/alerts/42"
            )

    async def test_get_paginated_resources(
        self, rest_client: GithubRestClient, mock_port_app_config: GithubPortAppConfig
    ) -> None:
        # Create an async mock to return the test alerts

        exporter = RestCodeScanningAlertExporter(rest_client)

        async def mock_paginated_request(
            *args: Any, **kwargs: Any
        ) -> AsyncGenerator[list[dict[str, Any]], None]:
            yield TEST_CODE_SCANNING_ALERTS

        with patch.object(
            rest_client, "send_paginated_request", side_effect=mock_paginated_request
        ) as mock_request:

            alerts = []
            async for batch in exporter.get_paginated_resources(
                ListCodeScanningAlertOptions(repo_name="test-repo", state="open")
            ):
                alerts.extend(batch)

            assert len(alerts) == 2
            assert all(alert["__repository"] == "test-repo" for alert in alerts)

            mock_request.assert_called_once_with(
                f"{rest_client.base_url}/repos/{rest_client.organization}/test-repo/code-scanning/alerts",
                {"state": "open"},
            )

    async def test_get_paginated_resources_with_state_filtering(
        self, rest_client: GithubRestClient
    ) -> None:
        # Test with different state options
        async def mock_paginated_request(
            *args: Any, **kwargs: Any
        ) -> AsyncGenerator[list[dict[str, Any]], None]:
            yield [TEST_CODE_SCANNING_ALERTS[0]]  # Only open alert

        with patch.object(
            rest_client, "send_paginated_request", side_effect=mock_paginated_request
        ) as mock_request:
            async with event_context("test_event"):
                options = ListCodeScanningAlertOptions(
                    repo_name="test-repo", state="open"
                )
                exporter = RestCodeScanningAlertExporter(rest_client)

                alerts: list[list[dict[str, Any]]] = [
                    batch async for batch in exporter.get_paginated_resources(options)
                ]

                assert len(alerts) == 1
                assert len(alerts[0]) == 1
                assert alerts[0][0]["state"] == "open"
                assert alerts[0][0]["__repository"] == "test-repo"

                mock_request.assert_called_once_with(
                    f"{rest_client.base_url}/repos/{rest_client.organization}/test-repo/code-scanning/alerts",
                    {"state": "open"},
                )

    async def test_get_resource_with_different_alert_number(
        self, rest_client: GithubRestClient
    ) -> None:
        exporter = RestCodeScanningAlertExporter(rest_client)

        with patch.object(
            rest_client, "send_api_request", new_callable=AsyncMock
        ) as mock_request:
            mock_request.return_value = TEST_CODE_SCANNING_ALERTS[1].copy()
            alert = await exporter.get_resource(
                SingleCodeScanningAlertOptions(repo_name="test-repo", alert_number="43")
            )

            expected_alert = {
                **TEST_CODE_SCANNING_ALERTS[1],
                "__repository": "test-repo",
            }
            assert alert == expected_alert
            assert alert["state"] == "dismissed"
            assert alert["dismissed_reason"] == "used_in_tests"

            mock_request.assert_called_once_with(
                f"{rest_client.base_url}/repos/{rest_client.organization}/test-repo/code-scanning/alerts/43"
            )
