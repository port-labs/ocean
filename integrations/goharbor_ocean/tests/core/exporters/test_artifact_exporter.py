from typing import Any, AsyncGenerator, Dict, List
from unittest.mock import Mock

import pytest

from harbor.clients.http.client import HarborClient
from harbor.core.exporters.artifact_exporter import HarborArtifactExporter


class TestHarborArtifactExporter:
    """Test cases for HarborArtifactExporter."""

    @pytest.fixture
    def mock_client(self) -> Any:
        """Create a mock Harbor client."""
        return Mock(spec=HarborClient)

    @pytest.fixture
    def exporter(self, mock_client: Any) -> HarborArtifactExporter:
        """Create a test exporter instance."""
        return HarborArtifactExporter(mock_client)

    @pytest.mark.asyncio
    async def test_get_paginated_resources_yields_artifact_batches(
        self, exporter: HarborArtifactExporter, mock_client: Any
    ) -> None:
        """Test get_paginated_resources yields batches of artifacts."""
        mock_artifacts: List[Dict[str, Any]] = [
            {"id": 1, "digest": "sha256:abc123"},
            {"id": 2, "digest": "sha256:def456"},
        ]

        async def mock_paginated_request(
            endpoint: str, params: Dict[str, Any]
        ) -> AsyncGenerator[List[Dict[str, Any]], None]:
            yield mock_artifacts

        object.__setattr__(mock_client, "send_paginated_request", mock_paginated_request)

        options = {"project_name": "test", "repository_name": "repo"}
        artifacts: List[Dict[str, Any]] = []
        async for batch in exporter.get_paginated_resources(options):
            artifacts.extend(batch)

        assert len(artifacts) == 2
        assert artifacts[0]["digest"] == "sha256:abc123"

    @pytest.mark.asyncio
    async def test_get_paginated_resources_raises_error_when_project_name_missing(
        self, exporter: HarborArtifactExporter, mock_client: Any
    ) -> None:
        """Test get_paginated_resources raises ValueError when project_name missing."""
        with pytest.raises(ValueError, match="project_name is required"):
            async for _ in exporter.get_paginated_resources({"repository_name": "repo"}):
                pass

    @pytest.mark.asyncio
    async def test_get_paginated_resources_raises_error_when_repository_name_missing(
        self, exporter: HarborArtifactExporter, mock_client: Any
    ) -> None:
        """Test get_paginated_resources raises ValueError when repository_name missing."""
        with pytest.raises(ValueError, match="repository_name is required"):
            async for _ in exporter.get_paginated_resources({"project_name": "test"}):
                pass

    @pytest.mark.asyncio
    async def test_get_paginated_resources_includes_enrichment_parameters(
        self, exporter: HarborArtifactExporter, mock_client: Any
    ) -> None:
        """Test get_paginated_resources includes enrichment parameters in request."""
        received_params = None

        async def mock_paginated_request(
            endpoint: str, params: Dict[str, Any]
        ) -> AsyncGenerator[List[Dict[str, Any]], None]:
            nonlocal received_params
            received_params = params
            yield []

        object.__setattr__(mock_client, "send_paginated_request", mock_paginated_request)

        options = {
            "project_name": "test",
            "repository_name": "repo",
            "with_tag": True,
            "with_scan_overview": True,
            "with_signature": True,
        }

        async for _ in exporter.get_paginated_resources(options):
            pass

        assert received_params["with_tag"] is True
        assert received_params["with_scan_overview"] is True
        assert received_params["with_signature"] is True
