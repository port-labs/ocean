import pytest
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch
import httpx

from client import ServicenowClient
from .conftest import (
    SAMPLE_USER_DATA,
    SAMPLE_INCIDENT_DATA,
    SAMPLE_VULNERABILITY_DATA,
)


class TestServicenowClient:
    """Test suite for ServiceNow client."""

    @pytest.mark.asyncio
    async def test_get_paginated_resource_single_page(
        self, servicenow_client: ServicenowClient
    ) -> None:
        """Test fetching a single page of resources."""
        mock_response = MagicMock()
        mock_response.json.return_value = {"result": [SAMPLE_USER_DATA]}
        mock_response.headers.get.return_value = ""
        mock_response.raise_for_status.return_value = None

        with patch.object(
            servicenow_client.http_client, "get", return_value=mock_response
        ):
            with patch.object(
                servicenow_client.authenticator,
                "get_headers",
                return_value={
                    "Authorization": "Basic dGVzdF91c2VyOnRlc3RfcGFzc3dvcmQ="
                },
            ):
                records: list[dict[str, Any]] = []
                async for batch in servicenow_client.get_paginated_resource(
                    resource_kind="sys_user"
                ):
                    records.extend(batch)

                assert len(records) == 1
                assert records[0]["sys_id"] == SAMPLE_USER_DATA["sys_id"]
                assert records[0]["user_name"] == "test.user"

    @pytest.mark.asyncio
    async def test_get_paginated_resource_with_pagination(
        self, servicenow_client: ServicenowClient
    ) -> None:
        """Test pagination handling with multiple pages."""
        # First page response
        first_page_response = MagicMock()
        first_page_response.json.return_value = {"result": [SAMPLE_USER_DATA]}
        first_page_response.headers.get.return_value = '<https://test-instance.service-now.com/api/now/table/sys_user?sysparm_limit=100&sysparm_offset=100>; rel="next"'
        first_page_response.raise_for_status.return_value = None

        # Second page response (last page)
        second_user = {
            **SAMPLE_USER_DATA,
            "sys_id": "another-user-id",
            "user_name": "another.user",
        }
        second_page_response = MagicMock()
        second_page_response.json.return_value = {"result": [second_user]}
        second_page_response.headers.get.return_value = ""
        second_page_response.raise_for_status.return_value = None

        with patch.object(
            servicenow_client.http_client,
            "get",
            side_effect=[first_page_response, second_page_response],
        ):
            with patch.object(
                servicenow_client.authenticator,
                "get_headers",
                return_value={
                    "Authorization": "Basic dGVzdF91c2VyOnRlc3RfcGFzc3dvcmQ="
                },
            ):
                records: list[dict[str, Any]] = []
                async for batch in servicenow_client.get_paginated_resource(
                    resource_kind="sys_user"
                ):
                    records.extend(batch)

                assert len(records) == 2
                assert records[0]["sys_id"] == SAMPLE_USER_DATA["sys_id"]
                assert records[1]["sys_id"] == "another-user-id"

    @pytest.mark.asyncio
    async def test_get_paginated_resource_with_query_params(
        self, servicenow_client: ServicenowClient
    ) -> None:
        """Test fetching resources with API query parameters."""
        mock_response = MagicMock()
        mock_response.json.return_value = {"result": [SAMPLE_INCIDENT_DATA]}
        mock_response.headers.get.return_value = ""
        mock_response.raise_for_status.return_value = None

        api_query_params = {
            "sysparm_display_value": "true",
            "sysparm_exclude_reference_link": "false",
            "sysparm_query": "state=2^severity=3",
            "sysparm_fields": "sys_id,number,short_description,state",
        }

        with patch.object(
            servicenow_client.http_client, "get", return_value=mock_response
        ):
            with patch.object(
                servicenow_client.authenticator,
                "get_headers",
                return_value={
                    "Authorization": "Basic dGVzdF91c2VyOnRlc3RfcGFzc3dvcmQ="
                },
            ):
                records: list[dict[str, Any]] = []
                async for batch in servicenow_client.get_paginated_resource(
                    resource_kind="incident", api_query_params=api_query_params
                ):
                    records.extend(batch)

                # Verify the request was made with correct params
                servicenow_client.http_client.get.assert_called_once()
                call_args = servicenow_client.http_client.get.call_args
                assert "incident" in call_args[1]["url"]
                assert (
                    call_args[1]["params"]["sysparm_query"]
                    == "state=2^severity=3^ORDERBYDESCsys_created_on"
                )
                assert call_args[1]["params"]["sysparm_limit"] == 100

    @pytest.mark.asyncio
    async def test_get_paginated_resource_vulnerabilities(
        self, servicenow_client: ServicenowClient
    ) -> None:
        """Test fetching vulnerabilities from sn_vuln_vulnerable_item table."""
        mock_response = MagicMock()
        mock_response.json.return_value = {"result": [SAMPLE_VULNERABILITY_DATA]}
        mock_response.headers.get.return_value = ""
        mock_response.raise_for_status.return_value = None

        with patch.object(
            servicenow_client.http_client, "get", return_value=mock_response
        ):
            with patch.object(
                servicenow_client.authenticator,
                "get_headers",
                return_value={
                    "Authorization": "Basic dGVzdF91c2VyOnRlc3RfcGFzc3dvcmQ="
                },
            ):
                vulnerabilities: list[dict[str, Any]] = []
                async for batch in servicenow_client.get_paginated_resource(
                    resource_kind="sn_vuln_vulnerable_item"
                ):
                    vulnerabilities.extend(batch)

                assert len(vulnerabilities) == 1
                assert (
                    vulnerabilities[0]["sys_id"] == SAMPLE_VULNERABILITY_DATA["sys_id"]
                )
                assert vulnerabilities[0]["state"] == "2"
                assert vulnerabilities[0]["severity"] == "3"
                assert vulnerabilities[0]["cvss_score"] == "7.5"

    @pytest.mark.asyncio
    async def test_get_paginated_resource_error_handling(
        self, servicenow_client: ServicenowClient
    ) -> None:
        """Test error handling when fetching resources fails."""
        # Mock HTTP error response
        error_response = MagicMock()
        error_response.status_code = 404
        error_response.text = "Table not found"
        error_response.raise_for_status.side_effect = httpx.HTTPStatusError(
            "Not Found", request=MagicMock(), response=error_response
        )

        with patch.object(
            servicenow_client.http_client, "get", return_value=error_response
        ):
            with patch.object(
                servicenow_client.authenticator,
                "get_headers",
                return_value={
                    "Authorization": "Basic dGVzdF91c2VyOnRlc3RfcGFzc3dvcmQ="
                },
            ):
                with pytest.raises(httpx.HTTPStatusError):
                    async for _ in servicenow_client.get_paginated_resource(
                        resource_kind="nonexistent_table"
                    ):
                        pass

    @pytest.mark.asyncio
    async def test_sanity_check_success(
        self, servicenow_client: ServicenowClient
    ) -> None:
        """Test successful sanity check."""
        mock_response = MagicMock()
        mock_response.json.return_value = {"result": [SAMPLE_USER_DATA]}
        mock_response.raise_for_status.return_value = None

        with patch.object(
            servicenow_client.http_client, "get", return_value=mock_response
        ) as mock_get:
            with patch.object(
                servicenow_client.authenticator,
                "get_headers",
                return_value={
                    "Authorization": "Basic dGVzdF91c2VyOnRlc3RfcGFzc3dvcmQ="
                },
            ):
                await servicenow_client.sanity_check()

                # Verify sanity check was called with correct endpoint
                mock_get.assert_called_once()
                call_args = mock_get.call_args
                # The get method is called with url as first positional arg
                if call_args[0]:
                    url = call_args[0][0]
                else:
                    url = call_args[1].get("url", "")
                assert "sys_user" in url
                # Check params if they exist
                if call_args[1] and "params" in call_args[1]:
                    assert call_args[1]["params"].get("sysparm_limit") == 1

    @pytest.mark.asyncio
    async def test_sanity_check_failure(
        self, servicenow_client: ServicenowClient
    ) -> None:
        """Test sanity check failure handling."""
        error_response = MagicMock()
        error_response.status_code = 401
        error_response.text = "Unauthorized"
        error_response.raise_for_status.side_effect = httpx.HTTPStatusError(
            "Unauthorized", request=MagicMock(), response=error_response
        )

        with patch.object(
            servicenow_client.http_client, "get", return_value=error_response
        ):
            with patch.object(
                servicenow_client.authenticator,
                "get_headers",
                return_value={
                    "Authorization": "Basic dGVzdF91c2VyOnRlc3RfcGFzc3dvcmQ="
                },
            ):
                with pytest.raises(httpx.HTTPStatusError):
                    await servicenow_client.sanity_check()

    def test_extract_next_link(self, servicenow_client: ServicenowClient) -> None:
        """Test extraction of next link from Link header."""
        # Test with next link
        link_header = (
            '<https://test-instance.service-now.com/api/now/table/sys_user?sysparm_limit=100&sysparm_offset=100>; rel="next", '
            '<https://test-instance.service-now.com/api/now/table/sys_user?sysparm_limit=100&sysparm_offset=0>; rel="first"'
        )
        next_link = servicenow_client.extract_next_link(link_header)
        assert (
            next_link
            == "https://test-instance.service-now.com/api/now/table/sys_user?sysparm_limit=100&sysparm_offset=100"
        )

        # Test without next link
        link_header_no_next = '<https://test-instance.service-now.com/api/now/table/sys_user?sysparm_limit=100&sysparm_offset=0>; rel="first"'
        next_link = servicenow_client.extract_next_link(link_header_no_next)
        assert next_link == ""

        # Test empty header
        next_link = servicenow_client.extract_next_link("")
        assert next_link == ""

    @pytest.mark.asyncio
    async def test_ensure_auth_headers(
        self, servicenow_client: ServicenowClient
    ) -> None:
        """Test that auth headers are properly set."""
        expected_headers = {"Authorization": "Basic dGVzdF91c2VyOnRlc3RfcGFzc3dvcmQ="}

        with patch.object(
            servicenow_client.authenticator,
            "get_headers",
            return_value=expected_headers,
        ):
            await servicenow_client._ensure_auth_headers()
            assert (
                servicenow_client.http_client.headers["Authorization"]
                == expected_headers["Authorization"]
            )

    @pytest.mark.asyncio
    async def test_get_paginated_resource_default_ordering(
        self, servicenow_client: ServicenowClient
    ) -> None:
        """Test that default ordering is applied when no query is provided."""
        mock_response = MagicMock()
        mock_response.json.return_value = {"result": [SAMPLE_USER_DATA]}
        mock_response.headers.get.return_value = ""
        mock_response.raise_for_status.return_value = None

        with patch.object(
            servicenow_client.http_client, "get", return_value=mock_response
        ):
            with patch.object(
                servicenow_client.authenticator,
                "get_headers",
                return_value={
                    "Authorization": "Basic dGVzdF91c2VyOnRlc3RfcGFzc3dvcmQ="
                },
            ):
                async for _ in servicenow_client.get_paginated_resource(
                    resource_kind="sys_user"
                ):
                    pass

                # Verify default ordering was added
                call_args = servicenow_client.http_client.get.call_args
                assert (
                    call_args[1]["params"]["sysparm_query"]
                    == "ORDERBYDESCsys_created_on"
                )

    @pytest.mark.asyncio
    async def test_get_paginated_resource_custom_ordering_preserved(
        self, servicenow_client: ServicenowClient
    ) -> None:
        """Test that custom ordering in query is preserved."""
        mock_response = MagicMock()
        mock_response.json.return_value = {"result": [SAMPLE_USER_DATA]}
        mock_response.headers.get.return_value = ""
        mock_response.raise_for_status.return_value = None

        api_query_params = {
            "sysparm_query": "active=true^ORDERBYuser_name",
        }

        with patch.object(
            servicenow_client.http_client, "get", return_value=mock_response
        ):
            with patch.object(
                servicenow_client.authenticator,
                "get_headers",
                return_value={
                    "Authorization": "Basic dGVzdF91c2VyOnRlc3RfcGFzc3dvcmQ="
                },
            ):
                async for _ in servicenow_client.get_paginated_resource(
                    resource_kind="sys_user", api_query_params=api_query_params
                ):
                    pass

                # Verify custom ordering was preserved and default was appended
                call_args = servicenow_client.http_client.get.call_args
                assert (
                    "active=true^ORDERBYuser_name^ORDERBYDESCsys_created_on"
                    in call_args[1]["params"]["sysparm_query"]
                )
