from typing import Any, List, Optional
from unittest.mock import MagicMock
import pytest
from gitlab_integration.gitlab_service import GitlabService


# Mock function simulating repository tree retrieval with pagination and path filtering
def mock_repository_tree(
    path: str, page: int, *args: Any, **kwargs: Any
) -> Optional[List[dict]]:
    if path == "src":
        if page == 1:
            return [
                {
                    "id": "fd581c619bf59cfdfa9c8282377bb09c2f897520",
                    "name": "markdown",
                    "type": "tree",
                    "path": "src/markdown",
                    "mode": "040000",
                }
            ]
        elif page == 2:
            return [
                {
                    "id": "23ea4d11a4bdd960ee5320c5cb65b5b3fdbc60db",
                    "name": "ruby",
                    "type": "tree",
                    "path": "src/ruby",
                    "mode": "040000",
                },
                {
                    "id": "e7e3e4c1b7a0a0d1e0c1f4e0a0d1e0c1f4e0a0d",
                    "name": "gitlab_ci.yml",
                    "type": "blob",
                    "path": "src/python",
                    "mode": "040000",
                },
            ]
        else:
            return []  # No more pages
    elif path == "files":
        if page == 1:
            return [
                {
                    "id": "4535904260b1082e14f867f7a24fd8c21495bde3",
                    "name": "images",
                    "type": "tree",
                    "path": "files/images",
                    "mode": "040000",
                }
            ]
        else:
            return []  # No more pages
    else:
        return []  # Path not found


@pytest.mark.asyncio
async def test_get_all_folders_in_project_path_with_folders(
    monkeypatch: Any, mocked_gitlab_service: GitlabService
) -> None:
    # Arrange
    mock_project = MagicMock()
    mock_project.path_with_namespace = "namespace/project"
    mock_project.default_branch = "main"
    mock_project.asdict.return_value = {
        "name": "namespace/project",
        "default_branch": "main",
    }

    mock_folder_selector = MagicMock()
    mock_folder_selector.path = "src"
    mock_folder_selector.branch = None

    monkeypatch.setattr(
        mock_project, "repository_tree", MagicMock(side_effect=mock_repository_tree)
    )

    expected_folders = [
        {
            "folder": {
                "id": "fd581c619bf59cfdfa9c8282377bb09c2f897520",
                "name": "markdown",
                "type": "tree",
                "path": "src/markdown",
                "mode": "040000",
            },
            "repo": mock_project.asdict(),
            "__branch": "main",
        },
        {
            "folder": {
                "id": "23ea4d11a4bdd960ee5320c5cb65b5b3fdbc60db",
                "name": "ruby",
                "type": "tree",
                "path": "src/ruby",
                "mode": "040000",
            },
            "repo": mock_project.asdict(),
            "__branch": "main",
        },
    ]

    # Act
    actual_folders = []
    async for folder_batch in mocked_gitlab_service.get_all_folders_in_project_path(
        mock_project, mock_folder_selector
    ):
        actual_folders.extend(folder_batch)

    # Assert
    assert actual_folders == expected_folders


@pytest.mark.asyncio
async def test_get_all_folders_in_project_path_no_folders(
    monkeypatch: Any, mocked_gitlab_service: GitlabService
) -> None:
    # Arrange
    mock_project = MagicMock()
    mock_project.path_with_namespace = "namespace/project"
    mock_project.default_branch = "main"
    mock_project.asdict.return_value = {
        "name": "namespace/project",
        "default_branch": "main",
    }

    mock_folder_selector = MagicMock()
    mock_folder_selector.path = "non_existing_path"  # No folders exist here
    mock_folder_selector.branch = None

    monkeypatch.setattr(
        mock_project, "repository_tree", MagicMock(side_effect=mock_repository_tree)
    )

    expected_folders: list[dict[str, Any]] = []

    # Act
    actual_folders = []
    async for folder_batch in mocked_gitlab_service.get_all_folders_in_project_path(
        mock_project, mock_folder_selector
    ):
        actual_folders.extend(folder_batch)

    # Assert
    assert actual_folders == expected_folders
