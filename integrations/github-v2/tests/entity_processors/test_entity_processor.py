from unittest.mock import AsyncMock, MagicMock, patch
import pytest

from github.entity_processors.entity_processor import FileEntityProcessor


@pytest.mark.asyncio
class TestFileEntityProcessor:
    @pytest.fixture
    def processor(self) -> FileEntityProcessor:
        """Create a FileEntityProcessor instance"""
        context = MagicMock()
        return FileEntityProcessor(context)

    async def test_search_with_repository_full_name(self, processor: FileEntityProcessor) -> None:
        """Test file search with repository full_name in data"""
        # Arrange
        data = {
            "full_name": "owner/repo",
            "default_branch": "main"
        }
        pattern = "file://README.md"
        expected_content = "# Test README"

        with patch("github.entity_processors.entity_processor.create_github_client") as mock_create_client:
            mock_client = MagicMock()
            mock_client.get_file_content = AsyncMock(return_value=expected_content)
            mock_create_client.return_value = mock_client

            # Act
            result = await processor._search(data, pattern)

            # Assert
            assert result == expected_content
            mock_client.get_file_content.assert_called_once_with(
                "owner/repo", "README.md", "main"
            )

    async def test_search_with_nested_repository(self, processor: FileEntityProcessor) -> None:
        """Test file search with repository in nested structure"""
        # Arrange
        data = {
            "repository": {
                "full_name": "owner/repo",
                "default_branch": "develop"
            }
        }
        pattern = "file://src/config.json"
        expected_content = '{"key": "value"}'

        with patch("github.entity_processors.entity_processor.create_github_client") as mock_create_client:
            mock_client = MagicMock()
            mock_client.get_file_content = AsyncMock(return_value=expected_content)
            mock_create_client.return_value = mock_client

            # Act
            result = await processor._search(data, pattern)

            # Assert
            assert result == expected_content
            mock_client.get_file_content.assert_called_once_with(
                "owner/repo", "src/config.json", "develop"
            )

    async def test_search_no_repository_path(self, processor: FileEntityProcessor) -> None:
        """Test file search when no repository path is found"""
        # Arrange
        data = {"id": 123}  # No full_name or repository
        pattern = "file://README.md"

        # Act & Assert
        with pytest.raises(ValueError, match="No repository path found in data"):
            await processor._search(data, pattern)
