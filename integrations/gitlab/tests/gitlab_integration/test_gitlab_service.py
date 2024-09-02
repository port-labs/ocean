from typing import Any
from unittest.mock import MagicMock

from gitlab_integration.gitlab_service import GitlabService


async def test_search_files_in_project(
    monkeypatch: Any,
    mocked_gitlab_service: GitlabService,
    mock_get_and_parse_single_file: Any,
) -> None:
    # Arrange
    search_pattern = "**/my/file.yaml"

    def mock_search(page: int, *args: Any, **kwargs: Any) -> Any:
        if page == 1:
            return [{"path": "hello/aaa/file.yaml"}]
        elif page == 2:
            return [
                {"path": "hello/my/file.yaml"},
                {"path": "hello/my/file2.yaml"},
                {"path": "hello/my/file3.yaml"},
            ]
        else:
            return None

    mock_project = MagicMock()
    monkeypatch.setattr(mock_project, "search", mock_search)

    # Act
    actual_files = []
    async for file in mocked_gitlab_service.search_files_in_project(
        mock_project, search_pattern
    ):
        actual_files.extend(file)

    # Assert
    assert len(actual_files) == 1
    assert actual_files[0] == "hello/my/file.yaml"
