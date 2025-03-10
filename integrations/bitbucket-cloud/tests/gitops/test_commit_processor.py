import pytest
from unittest.mock import AsyncMock, patch
from bitbucket_integration.gitops.commit_processor import process_single_file


@pytest.mark.asyncio
async def test_process_single_file() -> None:
    """Test processing a single file."""
    # Arrange
    mock_client = AsyncMock()
    updated_file = {
        "old": {"path": "specs/service.yml"},
        "new": {"path": "specs/service.yml"},
    }
    spec_paths = ["specs/"]

    with patch(
        "bitbucket_integration.gitops.commit_processor.match_spec_paths"
    ) as mock_match:
        mock_match.return_value = ["specs/service.yml"]
        with patch(
            "bitbucket_integration.gitops.commit_processor.process_file"
        ) as mock_process:
            mock_process.return_value = (["old_entity"], ["new_entity"])

            # Act
            old_entities, new_entities = await process_single_file(
                client=mock_client,
                repo="test-repo",
                updated_file=updated_file,
                spec_paths=spec_paths,
                old_hash="old-hash",
                new_hash="new-hash",
            )

            # Assert
            assert old_entities == ["old_entity"]
            assert new_entities == ["new_entity"]
            mock_match.assert_called_once()
            mock_process.assert_called_once()


@pytest.mark.asyncio
async def test_process_single_file_no_matching_paths() -> None:
    """Test processing a single file with no matching paths."""
    # Arrange
    mock_client = AsyncMock()
    updated_file = {
        "old": {"path": "src/service.js"},
        "new": {"path": "src/service.js"},
    }
    spec_paths = ["specs/"]

    with patch(
        "bitbucket_integration.gitops.commit_processor.match_spec_paths"
    ) as mock_match:
        # No matches found
        mock_match.return_value = []

        # Act
        old_entities, new_entities = await process_single_file(
            client=mock_client,
            repo="test-repo",
            updated_file=updated_file,
            spec_paths=spec_paths,
            old_hash="old-hash",
            new_hash="new-hash",
        )

        # Assert
        assert old_entities == []
        assert new_entities == []
        mock_match.assert_called_once()
