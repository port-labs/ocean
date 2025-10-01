import pytest
from unittest.mock import patch, AsyncMock
from github.entity_processors.file_entity_processor import FileEntityProcessor

MOCK_PORT_OCEAN_CONTEXT = AsyncMock()


@pytest.mark.asyncio
async def test_file_entity_processor_search_monorepo_success() -> None:
    data = {
        "repository": {"name": "test-repo", "default_branch": "main", "owner": {"login": "test-org"}},
        "branch": "develop",
        "metadata": {"path": "src/config.yaml"},
    }
    pattern = "file://config.json"
    expected_content = '{"key": "value"}'

    mock_exporter = AsyncMock()
    mock_exporter.get_resource.return_value = {
        "content": expected_content,
        "size": 20,
    }

    with patch(
        "github.entity_processors.file_entity_processor.RestFileExporter",
        return_value=mock_exporter,
    ):
        processor = FileEntityProcessor(context=MOCK_PORT_OCEAN_CONTEXT)
        result = await processor._search(data, pattern)
        assert result == expected_content
        mock_exporter.get_resource.assert_called_once_with(
            {
                "repo_name": "test-repo",
                "file_path": "src/config.json",
                "branch": "develop",
            }
        )


@pytest.mark.asyncio
async def test_file_entity_processor_search_non_monorepo_success() -> None:
    data = {
        "name": "test-repo",
        "default_branch": "main",
        "owner": {"login": "test-org"},
    }
    pattern = "file://README.md"
    expected_content = "plain text content"

    mock_exporter = AsyncMock()
    mock_exporter.get_resource.return_value = {
        "content": expected_content,
        "size": 50,
    }

    with patch(
        "github.entity_processors.file_entity_processor.RestFileExporter",
        return_value=mock_exporter,
    ):
        processor = FileEntityProcessor(context=MOCK_PORT_OCEAN_CONTEXT)
        result = await processor._search(data, pattern)
        assert result == expected_content
        mock_exporter.get_resource.assert_called_once_with(
            {
                "repo_name": "test-repo",
                "file_path": "README.md",
                "branch": "main",
            }
        )


@pytest.mark.asyncio
async def test_file_entity_processor_search_large_file() -> None:
    data = {
        "name": "test-repo",
        "default_branch": "main",
        "owner": {"login": "test-org"},
    }
    pattern = "file://large-file.txt"

    expected_content = None

    mock_exporter = AsyncMock()
    mock_exporter.get_resource.return_value = {
        "content": None,  # File too large
        "size": 1048577,
    }

    with patch(
        "github.entity_processors.file_entity_processor.RestFileExporter",
        return_value=mock_exporter,
    ):
        processor = FileEntityProcessor(context=MOCK_PORT_OCEAN_CONTEXT)
        result = await processor._search(data, pattern)
        assert result == expected_content


@pytest.mark.asyncio
async def test_file_entity_processor_search_error_handling() -> None:
    data = {
        "name": "test-repo",
        "default_branch": "main",
        "owner": {"login": "test-org"},
    }
    pattern = "file://config.json"

    mock_exporter = AsyncMock()
    # Simulate an exception when trying to get file content
    mock_exporter.get_resource.side_effect = Exception("Test exception")

    with patch(
        "github.entity_processors.file_entity_processor.RestFileExporter",
        return_value=mock_exporter,
    ):
        processor = FileEntityProcessor(context=MOCK_PORT_OCEAN_CONTEXT)
        # The actual implementation doesn't catch exceptions, so this should raise
        with pytest.raises(Exception, match="Test exception"):
            await processor._search(data, pattern)


@pytest.mark.asyncio
async def test_file_entity_processor_search_missing_repo_name() -> None:
    # Data without repository name
    data = {
        "default_branch": "main",
    }
    pattern = "file://config.json"

    processor = FileEntityProcessor(context=MOCK_PORT_OCEAN_CONTEXT)
    # The actual implementation doesn't handle missing keys gracefully
    with pytest.raises(KeyError, match="'name'"):
        await processor._search(data, pattern)


@pytest.mark.asyncio
async def test_file_entity_processor_search_missing_default_branch() -> None:
    # Data without default branch
    data = {
        "name": "test-repo",
        "owner": {"login": "test-org"},
    }
    pattern = "file://config.json"
    expected_content = '{"key": "value"}'

    mock_exporter = AsyncMock()
    mock_exporter.get_resource.return_value = {
        "content": expected_content,
        "size": 20,
    }

    with patch(
        "github.entity_processors.file_entity_processor.RestFileExporter",
        return_value=mock_exporter,
    ):
        processor = FileEntityProcessor(context=MOCK_PORT_OCEAN_CONTEXT)
        # The actual implementation uses .get() so it won't raise KeyError
        result = await processor._search(data, pattern)
        assert result == expected_content
        # Should use None as branch when default_branch is missing
        mock_exporter.get_resource.assert_called_once_with(
            {
                "repo_name": "test-repo",
                "file_path": "config.json",
                "branch": None,
            }
        )


@pytest.mark.asyncio
async def test_file_entity_processor_search_monorepo_missing_metadata_path() -> None:
    # Monorepo data without metadata path
    data = {
        "repository": {"name": "test-repo", "default_branch": "main", "owner": {"login": "test-org"}},
        "branch": "develop",
        "metadata": {},  # Missing path
    }
    pattern = "file://config.json"

    processor = FileEntityProcessor(context=MOCK_PORT_OCEAN_CONTEXT)
    # The actual implementation doesn't handle missing keys gracefully
    with pytest.raises(KeyError, match="'path'"):
        await processor._search(data, pattern)


@pytest.mark.asyncio
async def test_file_entity_processor_search_yaml_file() -> None:
    data = {
        "name": "test-repo",
        "default_branch": "main",
        "owner": {"login": "test-org"},
    }
    pattern = "file://config.yaml"
    expected_content = "name: test\nvalue: 123"

    mock_exporter = AsyncMock()
    mock_exporter.get_resource.return_value = {
        "content": expected_content,
        "size": 30,
    }

    with patch(
        "github.entity_processors.file_entity_processor.RestFileExporter",
        return_value=mock_exporter,
    ):
        processor = FileEntityProcessor(context=MOCK_PORT_OCEAN_CONTEXT)
        result = await processor._search(data, pattern)
        assert result == expected_content
        mock_exporter.get_resource.assert_called_once_with(
            {
                "repo_name": "test-repo",
                "file_path": "config.yaml",
                "branch": "main",
            }
        )


@pytest.mark.asyncio
async def test_file_entity_processor_search_nested_path() -> None:
    data = {
        "name": "test-repo",
        "default_branch": "main",
        "owner": {"login": "test-org"},
    }
    pattern = "file://src/config/app.json"
    expected_content = '{"app": "config"}'

    mock_exporter = AsyncMock()
    mock_exporter.get_resource.return_value = {
        "content": expected_content,
        "size": 25,
    }

    with patch(
        "github.entity_processors.file_entity_processor.RestFileExporter",
        return_value=mock_exporter,
    ):
        processor = FileEntityProcessor(context=MOCK_PORT_OCEAN_CONTEXT)
        result = await processor._search(data, pattern)
        assert result == expected_content
        mock_exporter.get_resource.assert_called_once_with(
            {
                "repo_name": "test-repo",
                "file_path": "src/config/app.json",
                "branch": "main",
            }
        )


@pytest.mark.asyncio
async def test_file_entity_processor_search_monorepo_nested_path() -> None:
    data = {
        "repository": {"name": "test-repo", "default_branch": "main", "owner": {"login": "test-org"}},
        "branch": "develop",
        "metadata": {"path": "services/auth/config.yaml"},
    }
    pattern = "file://app.json"
    expected_content = '{"service": "auth"}'

    mock_exporter = AsyncMock()
    mock_exporter.get_resource.return_value = {
        "content": expected_content,
        "size": 25,
    }

    with patch(
        "github.entity_processors.file_entity_processor.RestFileExporter",
        return_value=mock_exporter,
    ):
        processor = FileEntityProcessor(context=MOCK_PORT_OCEAN_CONTEXT)
        result = await processor._search(data, pattern)
        assert result == expected_content
        mock_exporter.get_resource.assert_called_once_with(
            {
                "repo_name": "test-repo",
                "file_path": "services/auth/app.json",
                "branch": "develop",
            }
        )


@pytest.mark.asyncio
async def test_file_entity_processor_get_file_content_success() -> None:
    processor = FileEntityProcessor(context=MOCK_PORT_OCEAN_CONTEXT)

    mock_exporter = AsyncMock()
    mock_exporter.get_resource.return_value = {
        "content": "test content",
        "size": 20,
    }

    with patch(
        "github.entity_processors.file_entity_processor.RestFileExporter",
        return_value=mock_exporter,
    ):
        result = await processor._get_file_content("test-repo", "config.json", "main")
        assert result == "test content"


@pytest.mark.asyncio
async def test_file_entity_processor_get_file_content_large_file() -> None:
    processor = FileEntityProcessor(context=MOCK_PORT_OCEAN_CONTEXT)

    mock_exporter = AsyncMock()
    mock_exporter.get_resource.return_value = {
        "content": None,  # File too large
        "size": 1048577,
    }

    with patch(
        "github.entity_processors.file_entity_processor.RestFileExporter",
        return_value=mock_exporter,
    ):
        result = await processor._get_file_content(
            "test-repo", "large-file.txt", "main"
        )
        # The actual implementation returns the content directly, even if it's None
        assert result is None


@pytest.mark.asyncio
async def test_file_entity_processor_get_file_content_error() -> None:
    processor = FileEntityProcessor(context=MOCK_PORT_OCEAN_CONTEXT)

    mock_exporter = AsyncMock()
    mock_exporter.get_resource.side_effect = Exception("API error")

    with patch(
        "github.entity_processors.file_entity_processor.RestFileExporter",
        return_value=mock_exporter,
    ):
        with pytest.raises(Exception, match="API error"):
            await processor._get_file_content("test-repo", "config.json", "main")
