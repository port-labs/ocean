from typing import Any, AsyncGenerator
import pytest
from unittest.mock import AsyncMock, patch
from github.core.exporters.secret_scanning_alert_exporter import (
    RestSecretScanningAlertExporter,
)
from github.core.options import (
    SingleSecretScanningAlertOptions,
    ListSecretScanningAlertOptions,
)
from github.clients.http.rest_client import GithubRestClient


TEST_SECRET_SCANNING_ALERTS = [
    {
        "number": 42,
        "created_at": "2020-06-19T11:21:34Z",
        "updated_at": "2020-06-19T11:21:34Z",
        "url": "https://api.github.com/repos/test-org/test-repo/secret-scanning/alerts/42",
        "html_url": "https://github.com/test-org/test-repo/security/secret-scanning/42",
        "state": "open",
        "resolution": None,
        "resolved_at": None,
        "resolved_by": None,
        "secret_type": "api_key",
        "secret": "ghp_1234567890abcdef",
        "location": {
            "type": "commit",
            "target": {
                "ref": "refs/heads/main",
                "sha": "47b6f9f4e8f7d7c8c1c4d5c6c7d8e9f0a1b2c3d4",
                "url": "https://api.github.com/repos/test-org/test-repo/commits/47b6f9f4e8f7d7c8c1c4d5c6c7d8e9f0a1b2c3d4",
            },
            "path": "config/api.js",
            "start_line": 15,
            "end_line": 15,
            "start_column": 20,
            "end_column": 45,
        },
        "validity": "active",
        "push_protection_bypassed": False,
        "push_protection_bypassed_at": None,
        "push_protection_bypassed_by": None,
    },
    {
        "number": 43,
        "created_at": "2020-06-19T11:21:34Z",
        "updated_at": "2020-06-19T11:21:34Z",
        "url": "https://api.github.com/repos/test-org/test-repo/secret-scanning/alerts/43",
        "html_url": "https://github.com/test-org/test-repo/security/secret-scanning/43",
        "state": "resolved",
        "resolution": "revoked",
        "resolved_at": "2020-06-19T11:21:34Z",
        "resolved_by": {
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
        "secret_type": "private_key",
        "secret": "-----BEGIN PRIVATE KEY-----\nMIIEvQIBADANBgkqhkiG9w0BAQEFAASCBKcwggSjAgEAAoIBAQC...\n-----END PRIVATE KEY-----",
        "location": {
            "type": "commit",
            "target": {
                "ref": "refs/heads/feature",
                "sha": "47b6f9f4e8f7d7c8c1c4d5c6c7d8e9f0a1b2c3d4",
                "url": "https://api.github.com/repos/test-org/test-repo/commits/47b6f9f4e8f7d7c8c1c4d5c6c7d8e9f0a1b2c3d4",
            },
            "path": "keys/private.pem",
            "start_line": 1,
            "end_line": 10,
            "start_column": 1,
            "end_column": 50,
        },
        "validity": "inactive",
        "push_protection_bypassed": False,
        "push_protection_bypassed_at": None,
        "push_protection_bypassed_by": None,
    },
]


@pytest.mark.asyncio
class TestRestSecretScanningAlertExporter:
    async def test_get_resource(self, rest_client: GithubRestClient) -> None:
        exporter = RestSecretScanningAlertExporter(rest_client)

        with patch.object(
            rest_client, "send_api_request", new_callable=AsyncMock
        ) as mock_request:
            mock_request.return_value = TEST_SECRET_SCANNING_ALERTS[0].copy()
            alert = await exporter.get_resource(
                SingleSecretScanningAlertOptions(
                    organization="test-org",
                    repo_name="test-repo",
                    alert_number="42",
                    hide_secret=True,
                )
            )

            # Verify the __repository field was added
            expected_alert = {
                **TEST_SECRET_SCANNING_ALERTS[0],
                "__repository": "test-repo",
                "__organization": "test-org",
            }
            assert alert == expected_alert

            mock_request.assert_called_once_with(
                f"{rest_client.base_url}/repos/test-org/test-repo/secret-scanning/alerts/42",
                {"hide_secret": True},  # hide_secret parameter
            )

    async def test_get_paginated_resources(self, rest_client: GithubRestClient) -> None:
        exporter = RestSecretScanningAlertExporter(rest_client)

        async def mock_paginated_request(
            *args: Any, **kwargs: Any
        ) -> AsyncGenerator[list[dict[str, Any]], None]:
            yield TEST_SECRET_SCANNING_ALERTS

        with patch.object(
            rest_client, "send_paginated_request", side_effect=mock_paginated_request
        ) as mock_request:

            alerts = []
            async for batch in exporter.get_paginated_resources(
                ListSecretScanningAlertOptions(
                    organization="test-org",
                    repo_name="test-repo",
                    state="open",
                    hide_secret=True,
                )
            ):
                alerts.extend(batch)

            assert len(alerts) == 2
            assert all(alert["__repository"] == "test-repo" for alert in alerts)
            assert all(alert["__organization"] == "test-org" for alert in alerts)

            mock_request.assert_called_once_with(
                f"{rest_client.base_url}/repos/test-org/test-repo/secret-scanning/alerts",
                {"state": "open", "hide_secret": True},
            )

    async def test_get_paginated_resources_with_all_state(
        self, rest_client: GithubRestClient
    ) -> None:
        exporter = RestSecretScanningAlertExporter(rest_client)

        async def mock_paginated_request(
            *args: Any, **kwargs: Any
        ) -> AsyncGenerator[list[dict[str, Any]], None]:
            yield TEST_SECRET_SCANNING_ALERTS

        with patch.object(
            rest_client, "send_paginated_request", side_effect=mock_paginated_request
        ) as mock_request:

            alerts = []
            async for batch in exporter.get_paginated_resources(
                ListSecretScanningAlertOptions(
                    organization="test-org",
                    repo_name="test-repo",
                    state="all",
                    hide_secret=True,
                )
            ):
                alerts.extend(batch)

            # When state is "all", it should be removed from params
            expected_params = {"hide_secret": True}
            assert len(alerts) == 2
            assert all(alert["__repository"] == "test-repo" for alert in alerts)
            assert all(alert["__organization"] == "test-org" for alert in alerts)

            mock_request.assert_called_once_with(
                f"{rest_client.base_url}/repos/test-org/test-repo/secret-scanning/alerts",
                expected_params,
            )
