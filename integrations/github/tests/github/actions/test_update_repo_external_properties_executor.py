"""Tests for UpdateRepoExternalPropertiesExecutor."""

import pytest
import httpx
from unittest.mock import AsyncMock, MagicMock, patch

from github.actions.update_repo_external_properties_executor import (
    UpdateRepoExternalPropertiesExecutor,
    _extract_changed_properties,
    _build_github_properties_payload,
)
from github.helpers.exceptions import InvalidActionParametersException
from port_ocean.core.models import ActionRun, IntegrationActionInvocationPayload


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def make_run(execution_properties: dict) -> ActionRun:
    return ActionRun(
        id="run-123",
        status="IN_PROGRESS",
        payload=IntegrationActionInvocationPayload(
            type="INTEGRATION_ACTION",
            installationId="inst-1",
            integrationActionType="update_repo_external_properties",
            integrationActionExecutionProperties=execution_properties,
        ),
    )


# ---------------------------------------------------------------------------
# Unit tests — pure helpers
# ---------------------------------------------------------------------------


class TestExtractChangedProperties:
    def test_returns_changed_values(self):
        diff = {
            "before": {"properties": {"lifecycle": "Production", "tier": "1"}},
            "after": {"properties": {"lifecycle": "Deprecated", "tier": "1"}},
        }
        result = _extract_changed_properties(diff)
        assert result == {"lifecycle": "Deprecated"}

    def test_includes_new_properties(self):
        diff = {
            "before": {"properties": {}},
            "after": {"properties": {"newProp": "value"}},
        }
        result = _extract_changed_properties(diff)
        assert result == {"newProp": "value"}

    def test_skips_port_meta_properties(self):
        diff = {
            "before": {"properties": {"title": "old", "lifecycle": "A"}},
            "after": {"properties": {"title": "new", "lifecycle": "B"}},
        }
        result = _extract_changed_properties(diff)
        assert "title" not in result
        assert result == {"lifecycle": "B"}

    def test_unchanged_values_excluded(self):
        diff = {
            "before": {"properties": {"foo": "same"}},
            "after": {"properties": {"foo": "same"}},
        }
        assert _extract_changed_properties(diff) == {}

    def test_empty_diff(self):
        assert _extract_changed_properties({}) == {}

    def test_none_after_value(self):
        diff = {
            "before": {"properties": {"prop": "val"}},
            "after": {"properties": {"prop": None}},
        }
        result = _extract_changed_properties(diff)
        assert result == {"prop": None}

    def test_removed_property_becomes_null(self):
        diff = {
            "before": {"properties": {"lifecycle": "Production", "tier": "1"}},
            "after": {"properties": {"tier": "1"}},
        }
        result = _extract_changed_properties(diff)
        assert result == {"lifecycle": None}

    def test_removed_meta_property_skipped(self):
        diff = {
            "before": {"properties": {"title": "old", "lifecycle": "A"}},
            "after": {"properties": {"lifecycle": "A"}},
        }
        result = _extract_changed_properties(diff)
        assert "title" not in result
        assert result == {}


class TestBuildGithubPropertiesPayload:
    def test_string_value(self):
        payload = _build_github_properties_payload({"lifecycle": "Deprecated"})
        assert payload == [{"property_name": "lifecycle", "value": "Deprecated"}]

    def test_list_value_stringified(self):
        payload = _build_github_properties_payload({"tags": ["a", "b"]})
        assert payload == [{"property_name": "tags", "value": "['a', 'b']"}]

    def test_none_value(self):
        payload = _build_github_properties_payload({"prop": None})
        assert payload == [{"property_name": "prop", "value": None}]

    def test_non_string_value_coerced_to_str(self):
        payload = _build_github_properties_payload({"count": 42})
        assert payload == [{"property_name": "count", "value": "42"}]

    def test_bool_value_coerced_to_str(self):
        payload = _build_github_properties_payload({"active": True})
        assert payload == [{"property_name": "active", "value": "True"}]

    def test_multiple_properties_order_preserved(self):
        changed = {"a": "1", "b": "2"}
        payload = _build_github_properties_payload(changed)
        names = [p["property_name"] for p in payload]
        assert names == ["a", "b"]


# ---------------------------------------------------------------------------
# Integration tests — executor.execute()
# ---------------------------------------------------------------------------


@pytest.fixture
def mock_rest_client():
    client = MagicMock()
    client.base_url = "https://api.github.com"
    client.make_request = AsyncMock()
    client.get_rate_limit_status = MagicMock(return_value=None)
    return client


@pytest.fixture
def mock_port_client():
    pc = MagicMock()
    pc.post_run_log = AsyncMock()
    pc.report_run_completed = AsyncMock()
    return pc


@pytest.fixture
def executor(mock_rest_client):
    with patch(
        "github.actions.abstract_github_executor.create_github_client",
        return_value=mock_rest_client,
    ):
        return UpdateRepoExternalPropertiesExecutor()


class TestUpdateRepoExternalPropertiesExecutor:
    @pytest.mark.asyncio
    async def test_happy_path(self, executor, mock_rest_client, mock_port_client):
        run = make_run(
            {
                "org": "port-labs",
                "repo": "ocean",
                "diff": {
                    "before": {"properties": {"lifecycle": "Production"}},
                    "after": {"properties": {"lifecycle": "Deprecated"}},
                },
            }
        )

        with patch("github.actions.update_repo_external_properties_executor.ocean") as mock_ocean:
            mock_ocean.port_client = mock_port_client
            await executor.execute(run)

        mock_rest_client.make_request.assert_awaited_once()
        call_kwargs = mock_rest_client.make_request.call_args
        assert "orgs/port-labs/properties/external/values" in call_kwargs.args[0]
        assert call_kwargs.kwargs["method"] == "PATCH"
        json_data = call_kwargs.kwargs["json_data"]
        assert json_data["repository_names"] == ["ocean"]
        assert json_data["properties"] == [{"property_name": "lifecycle", "value": "Deprecated"}]

        mock_port_client.report_run_completed.assert_awaited_once_with(
            run, success=True, message="Updated 1 external property(s) on port-labs/ocean."
        )

    @pytest.mark.asyncio
    async def test_no_changes_skips_github_call(self, executor, mock_rest_client, mock_port_client):
        run = make_run(
            {
                "org": "port-labs",
                "repo": "ocean",
                "diff": {
                    "before": {"properties": {"lifecycle": "Production"}},
                    "after": {"properties": {"lifecycle": "Production"}},
                },
            }
        )

        with patch("github.actions.update_repo_external_properties_executor.ocean") as mock_ocean:
            mock_ocean.port_client = mock_port_client
            await executor.execute(run)

        mock_rest_client.make_request.assert_not_awaited()
        mock_port_client.report_run_completed.assert_awaited_once_with(
            run, success=True, message="No changes to apply."
        )

    @pytest.mark.asyncio
    async def test_missing_org_raises(self, executor, mock_port_client):
        run = make_run({"repo": "ocean", "diff": {}})

        with pytest.raises(InvalidActionParametersException, match="'org' and 'repo'"):
            with patch("github.actions.update_repo_external_properties_executor.ocean") as mock_ocean:
                mock_ocean.port_client = mock_port_client
                await executor.execute(run)

    @pytest.mark.asyncio
    async def test_missing_diff_raises(self, executor, mock_port_client):
        run = make_run({"org": "port-labs", "repo": "ocean"})

        with pytest.raises(InvalidActionParametersException, match="'diff'"):
            with patch("github.actions.update_repo_external_properties_executor.ocean") as mock_ocean:
                mock_ocean.port_client = mock_port_client
                await executor.execute(run)

    @pytest.mark.asyncio
    async def test_github_http_error_raises(self, executor, mock_rest_client, mock_port_client):
        run = make_run(
            {
                "org": "port-labs",
                "repo": "ocean",
                "diff": {
                    "before": {"properties": {}},
                    "after": {"properties": {"tier": "1"}},
                },
            }
        )

        # Build a realistic HTTPStatusError
        request = httpx.Request("PATCH", "https://api.github.com/orgs/port-labs/properties/external/values")
        response = httpx.Response(422, json={"message": "Unprocessable Entity"}, request=request)
        mock_rest_client.make_request.side_effect = httpx.HTTPStatusError(
            "422", request=request, response=response
        )

        with pytest.raises(Exception, match="Unprocessable Entity"):
            with patch("github.actions.update_repo_external_properties_executor.ocean") as mock_ocean:
                mock_ocean.port_client = mock_port_client
                await executor.execute(run)

    def test_action_name(self, executor):
        assert executor.ACTION_NAME == "update_repo_external_properties"
