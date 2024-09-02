from typing import Any
from unittest.mock import MagicMock
from gitlab.v4.objects import ProjectFile
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
    expected_files = ["hello/my/file.yaml"]
    # Act
    actual_files = []
    async for file in mocked_gitlab_service.search_files_in_project(
        mock_project, search_pattern
    ):
        actual_files.extend(file)

    # Assert
    assert len(actual_files) == 1
    assert actual_files == expected_files


async def test_get_and_parse_single_file(
    monkeypatch: Any, mocked_gitlab_service: GitlabService
) -> None:
    # Arrange
    mock_file = MagicMock()
    monkeypatch.setattr(mock_file, "size", 1)
    mock_file.decode.return_value = "file content"
    mock_file.asdict.return_value = {"content": "this should be overwritten"}

    mock_project = MagicMock()
    mock_project.files.get.return_value = mock_file
    mock_project.asdict.return_value = "project data"

    expected_parsed_single_file = {
        "file": {"content": "file content"},
        "repo": "project data",
    }

    # Act
    actual_parsed_single_file = await mocked_gitlab_service.get_and_parse_single_file(
        mock_project, "path", "branch"
    )

    # Assert
    assert expected_parsed_single_file == actual_parsed_single_file


async def test_get_and_parse_single_file_yaml(
    monkeypatch: Any, mocked_gitlab_service: GitlabService
) -> None:
    # Arrange
    mock_file = MagicMock()
    monkeypatch.setattr(mock_file, "size", 1)
    monkeypatch.setattr(
        mock_file,
        "decode",
        lambda: """project: data
hello:
    value: world""",
    )
    mock_file.asdict.return_value = {"content": "this should be overwritten"}

    mock_project = MagicMock()
    mock_project.files.get.return_value = mock_file
    mock_project.asdict.return_value = "project data"

    expected_parsed_single_file = {
        "file": {"content": {"project": "data", "hello": {"value": "world"}}},
        "repo": "project data",
    }

    # Act
    actual_parsed_single_file = await mocked_gitlab_service.get_and_parse_single_file(
        mock_project, "path", "branch"
    )

    # Assert
    assert expected_parsed_single_file == actual_parsed_single_file
