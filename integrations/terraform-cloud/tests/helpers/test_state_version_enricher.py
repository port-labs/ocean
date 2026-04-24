from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from helpers.state_version_enricher import enrich_state_versions_with_output_data


@pytest.fixture
def mock_terraform_client() -> MagicMock:
    return MagicMock()


class TestEnrichStateVersionsWithOutputData:
    @pytest.mark.asyncio
    async def test_enrich_state_versions_success(
        self, mock_terraform_client: Any
    ) -> None:
        state_versions = [
            {"id": "sv-1", "attributes": {"status": "finalized"}},
            {"id": "sv-2", "attributes": {"status": "current"}},
        ]
        output_data = [
            {"name": "output1", "value": "value1"},
            {"name": "output2", "value": "value2"},
        ]

        mock_terraform_client.get_state_version_output = AsyncMock(
            side_effect=output_data
        )

        result = await enrich_state_versions_with_output_data(
            mock_terraform_client, state_versions
        )

        assert len(result) == 2
        assert result[0]["__output"] == output_data[0]
        assert result[1]["__output"] == output_data[1]
        assert result[0]["id"] == "sv-1"
        assert result[1]["id"] == "sv-2"

    @pytest.mark.asyncio
    async def test_enrich_state_versions_empty_list(
        self, mock_terraform_client: Any
    ) -> None:
        result = await enrich_state_versions_with_output_data(mock_terraform_client, [])

        assert result == []

    @pytest.mark.asyncio
    async def test_enrich_state_versions_with_api_failure(
        self, mock_terraform_client: Any
    ) -> None:
        state_versions = [
            {"id": "sv-1", "attributes": {"status": "finalized"}},
            {"id": "sv-2", "attributes": {"status": "current"}},
        ]

        mock_terraform_client.get_state_version_output = AsyncMock(
            side_effect=[{"name": "output1"}, Exception("API Error")]
        )

        result = await enrich_state_versions_with_output_data(
            mock_terraform_client, state_versions
        )

        assert len(result) == 2
        assert result[0]["__output"] == {"name": "output1"}
        assert result[1]["__output"] == {}

    @pytest.mark.asyncio
    async def test_enrich_state_versions_preserves_original_data(
        self, mock_terraform_client: Any
    ) -> None:
        state_versions = [
            {
                "id": "sv-1",
                "attributes": {"status": "finalized", "serial": 123},
                "relationships": {"workspace": {"data": {"id": "ws-1"}}},
            }
        ]
        output_data = {"name": "output1", "value": "value1"}

        mock_terraform_client.get_state_version_output = AsyncMock(
            return_value=output_data
        )

        result = await enrich_state_versions_with_output_data(
            mock_terraform_client, state_versions
        )

        assert result[0]["id"] == "sv-1"
        assert result[0]["attributes"]["status"] == "finalized"
        assert result[0]["attributes"]["serial"] == 123
        assert result[0]["__output"] == output_data
