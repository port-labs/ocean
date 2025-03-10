import pytest
from unittest.mock import AsyncMock, patch
from bitbucket_integration.gitops.file_processor import (
    determine_file_action,
    process_file,
)


def test_determine_file_action() -> None:
    """Test determining file action from diff stats."""
    result = determine_file_action(
        {"old": {"path": "old.yaml"}, "new": {"path": "new.yaml"}}
    )
    assert result[0] == "modified"  # Action type is correct
    assert "old.yaml" in result  # Contains old path
    assert "new.yaml" in result  # Contains new path

    result = determine_file_action({"old": {"path": "old.yaml"}, "new": None})
    assert result[0] == "deleted"
    assert "old.yaml" in result
    assert "new.yaml" not in result

    result = determine_file_action({"old": None, "new": {"path": "new.yaml"}})
    assert result[0] == "added"
    assert "old.yaml" not in result
    assert "new.yaml" in result


@pytest.mark.asyncio
async def test_process_file_deleted() -> None:
    """Test processing a deleted file."""
    mock_client = AsyncMock()
    mock_client.get_file_content.return_value = "old content"

    with patch(
        "bitbucket_integration.gitops.file_processor.generate_entities_from_yaml_file"
    ) as mock_generate:
        mock_generate.return_value = ["old_entity"]

        old_entities, new_entities = await process_file(
            client=mock_client,
            repo="test-repo",
            action="deleted",
            old_file_path="specs/file.yaml",
            new_file_path="",
            old_hash="old-hash",
            new_hash="new-hash",
        )

        assert old_entities == ["old_entity"]
        assert new_entities == []
        mock_client.get_file_content.assert_called_once_with(
            "test-repo", "old-hash", "specs/file.yaml"
        )


@pytest.mark.asyncio
async def test_process_file_added() -> None:
    """Test processing an added file."""
    mock_client = AsyncMock()
    mock_client.get_file_content.return_value = "new content"

    with patch(
        "bitbucket_integration.gitops.file_processor.generate_entities_from_yaml_file"
    ) as mock_generate:
        mock_generate.return_value = ["new_entity"]

        old_entities, new_entities = await process_file(
            client=mock_client,
            repo="test-repo",
            action="added",
            old_file_path="",
            new_file_path="specs/file.yaml",
            old_hash="old-hash",
            new_hash="new-hash",
        )

        assert old_entities == []
        assert new_entities == ["new_entity"]
        mock_client.get_file_content.assert_called_once_with(
            "test-repo", "new-hash", "specs/file.yaml"
        )


@pytest.mark.asyncio
async def test_process_file_modified() -> None:
    """Test processing a modified file."""
    mock_client = AsyncMock()
    mock_client.get_file_content.side_effect = ["old content", "new content"]

    with patch(
        "bitbucket_integration.gitops.file_processor.generate_entities_from_yaml_file"
    ) as mock_generate:
        mock_generate.side_effect = [["old_entity"], ["new_entity"]]

        old_entities, new_entities = await process_file(
            client=mock_client,
            repo="test-repo",
            action="modified",
            old_file_path="specs/old.yaml",
            new_file_path="specs/new.yaml",
            old_hash="old-hash",
            new_hash="new-hash",
        )

        assert old_entities == ["old_entity"]
        assert new_entities == ["new_entity"]
        assert mock_client.get_file_content.call_count == 2
