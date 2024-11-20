from typing import Any
from unittest.mock import AsyncMock
import pytest

from gitlab_integration.gitlab_service import GitlabService


@pytest.fixture
def mocked_gitlab_service() -> GitlabService:
    mock_gitlab_client: AsyncMock = AsyncMock()
    # Create an instance of GitlabService with the mocked gitlab_client
    return GitlabService(
        gitlab_client=mock_gitlab_client,
        app_host="http://example.com",  # Mock app host
        group_mapping=["group1", "group2"],  # Mock group mappings
    )


@pytest.fixture
def mock_get_and_parse_single_file(
    monkeypatch: Any, mocked_gitlab_service: GitlabService
) -> None:
    async def mock_get_and_parse_single_file(
        project: Any, file_path: str, branch: str
    ) -> Any:
        return file_path

    monkeypatch.setattr(
        mocked_gitlab_service,
        "get_and_parse_single_file",
        mock_get_and_parse_single_file,
    )
