from typing import Any, AsyncGenerator
import pytest
from unittest.mock import AsyncMock, patch, MagicMock
import httpx
from github.core.exporters.dependabot_exporter import (
    RestDependabotAlertExporter,
)
from integration import GithubPortAppConfig
from port_ocean.context.event import event_context
from github.core.options import SingleDependabotAlertOptions, ListDependabotAlertOptions
from github.clients.http.rest_client import GithubRestClient


TEST_DEPENDABOT_ALERTS = [
    {
        "number": 1,
        "state": "open",
        "dependency": {
            "package": {"ecosystem": "npm", "name": "lodash"},
            "manifest_path": "package.json",
            "scope": "runtime",
        },
        "security_advisory": {
            "ghsa_id": "GHSA-jf85-cpcp-j695",
            "cve_id": "CVE-2019-10744",
            "severity": "high",
            "summary": "Prototype Pollution in lodash",
            "description": "Versions of lodash prior to 4.17.12 are vulnerable to Prototype Pollution.",
            "vulnerabilities": [
                {
                    "package": {"ecosystem": "npm", "name": "lodash"},
                    "severity": "high",
                    "vulnerable_version_range": "< 4.17.12",
                    "first_patched_version": {"identifier": "4.17.12"},
                }
            ],
            "references": [{"url": "https://nvd.nist.gov/vuln/detail/CVE-2019-10744"}],
            "published_at": "2019-07-26T16:10:00Z",
            "updated_at": "2021-01-08T19:02:13Z",
            "withdrawn_at": None,
        },
        "url": "https://api.github.com/repos/test-org/test-repo/dependabot/alerts/1",
        "html_url": "https://github.com/test-org/test-repo/security/dependabot/1",
        "created_at": "2019-01-02T19:23:10Z",
        "updated_at": "2019-01-02T19:23:10Z",
        "dismissed_at": None,
        "dismissed_by": None,
        "dismissed_reason": None,
        "dismissed_comment": None,
        "fixed_at": None,
    },
    {
        "number": 2,
        "state": "dismissed",
        "dependency": {
            "package": {"ecosystem": "npm", "name": "debug"},
            "manifest_path": "package.json",
            "scope": "runtime",
        },
        "security_advisory": {
            "ghsa_id": "GHSA-gxpj-cx7g-858c",
            "cve_id": "CVE-2017-20165",
            "severity": "medium",
            "summary": "Regular Expression Denial of Service in debug",
            "description": "Affected versions of `debug` are vulnerable to regular expression denial of service",
            "vulnerabilities": [
                {
                    "package": {"ecosystem": "npm", "name": "debug"},
                    "severity": "medium",
                    "vulnerable_version_range": "<= 2.6.8 || >= 3.0.0 <= 3.0.1",
                    "first_patched_version": {"identifier": "2.6.9"},
                }
            ],
            "references": [{"url": "https://nvd.nist.gov/vuln/detail/CVE-2017-20165"}],
            "published_at": "2018-01-22T13:32:00Z",
            "updated_at": "2021-01-08T18:58:50Z",
            "withdrawn_at": None,
        },
        "url": "https://api.github.com/repos/test-org/test-repo/dependabot/alerts/2",
        "html_url": "https://github.com/test-org/test-repo/security/dependabot/2",
        "created_at": "2018-01-22T19:23:10Z",
        "updated_at": "2019-01-02T19:23:10Z",
        "dismissed_at": "2019-01-02T19:23:10Z",
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
        "dismissed_reason": "no_bandwidth",
        "dismissed_comment": "This vulnerability is in our test dependencies",
        "fixed_at": None,
    },
]


@pytest.mark.asyncio
class TestRestDependabotAlertExporter:
    async def test_get_resource(self, rest_client: GithubRestClient) -> None:
        # Create a mock response
        mock_response = MagicMock(spec=httpx.Response)
        mock_response.status_code = 200
        mock_response.json.return_value = TEST_DEPENDABOT_ALERTS[0]

        exporter = RestDependabotAlertExporter(rest_client)

        with patch.object(
            rest_client, "send_api_request", new_callable=AsyncMock
        ) as mock_request:
            mock_request.return_value = TEST_DEPENDABOT_ALERTS[0].copy()
            alert = await exporter.get_resource(
                SingleDependabotAlertOptions(repo_name="test-repo", alert_number="1")
            )

            # Verify the repo field was added
            expected_alert = {
                **TEST_DEPENDABOT_ALERTS[0],
                "__repository": "test-repo",
            }
            assert alert == expected_alert

            mock_request.assert_called_once_with(
                f"{rest_client.base_url}/repos/{rest_client.organization}/test-repo/dependabot/alerts/1"
            )

    async def test_get_paginated_resources(
        self, rest_client: GithubRestClient, mock_port_app_config: GithubPortAppConfig
    ) -> None:
        # Create an async mock to return the test alerts

        exporter = RestDependabotAlertExporter(rest_client)

        async def mock_paginated_request(
            *args: Any, **kwargs: Any
        ) -> AsyncGenerator[list[dict[str, Any]], None]:
            yield TEST_DEPENDABOT_ALERTS

        with patch.object(
            rest_client, "send_paginated_request", side_effect=mock_paginated_request
        ) as mock_request:
            alerts = []
            async for batch in exporter.get_paginated_resources(
                ListDependabotAlertOptions(
                    repo_name="test-repo", state=["open", "dismissed"]
                )
            ):
                alerts.extend(batch)

            assert len(alerts) == 2
            assert all(alert["__repository"] == "test-repo" for alert in alerts)

            mock_request.assert_called_once_with(
                f"{rest_client.base_url}/repos/{rest_client.organization}/test-repo/dependabot/alerts",
                {"state": "open,dismissed"},
            )

    async def test_get_paginated_resources_with_state_filtering(
        self, rest_client: GithubRestClient
    ) -> None:
        # Test with different state options
        async def mock_paginated_request(
            *args: Any, **kwargs: Any
        ) -> AsyncGenerator[list[dict[str, Any]], None]:
            yield [TEST_DEPENDABOT_ALERTS[0]]  # Only open alert

        with patch.object(
            rest_client, "send_paginated_request", side_effect=mock_paginated_request
        ) as mock_request:
            async with event_context("test_event"):
                options = ListDependabotAlertOptions(
                    repo_name="test-repo", state=["open"]
                )
                exporter = RestDependabotAlertExporter(rest_client)

                alerts: list[list[dict[str, Any]]] = [
                    batch async for batch in exporter.get_paginated_resources(options)
                ]

                assert len(alerts) == 1
                assert len(alerts[0]) == 1
                assert alerts[0][0]["state"] == "open"
                assert alerts[0][0]["__repository"] == "test-repo"

                mock_request.assert_called_once_with(
                    f"{rest_client.base_url}/repos/{rest_client.organization}/test-repo/dependabot/alerts",
                    {"state": "open"},
                )

    async def test_get_resource_with_different_alert_number(
        self, rest_client: GithubRestClient
    ) -> None:
        exporter = RestDependabotAlertExporter(rest_client)

        with patch.object(
            rest_client, "send_api_request", new_callable=AsyncMock
        ) as mock_request:
            mock_request.return_value = TEST_DEPENDABOT_ALERTS[1].copy()
            alert = await exporter.get_resource(
                SingleDependabotAlertOptions(repo_name="test-repo", alert_number="2")
            )

            expected_alert = {
                **TEST_DEPENDABOT_ALERTS[1],
                "__repository": "test-repo",
            }
            assert alert == expected_alert
            assert alert["state"] == "dismissed"
            assert alert["dismissed_reason"] == "no_bandwidth"

            mock_request.assert_called_once_with(
                f"{rest_client.base_url}/repos/{rest_client.organization}/test-repo/dependabot/alerts/2"
            )
