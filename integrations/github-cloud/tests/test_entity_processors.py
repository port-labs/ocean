import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from github_cloud.entity_processors.entity_processor import FileEntityProcessor, SearchEntityProcessor, FILE_PROPERTY_PREFIX, SEARCH_PROPERTY_PREFIX

@pytest.fixture
def mock_context():
    return MagicMock()

@pytest.fixture
def mock_github_client():
    with patch("github_cloud.entity_processors.entity_processor.create_github_client") as mock:
        client = AsyncMock()
        mock.return_value = client
        yield client

@pytest.mark.asyncio
async def test_file_entity_processor_success(mock_github_client, mock_context):
    processor = FileEntityProcessor(context=mock_context)
    data = {
        "full_name": "owner/repo",
        "default_branch": "main"
    }
    pattern = f"{FILE_PROPERTY_PREFIX}path/to/file.txt"
    expected_content = "test content"

    mock_github_client.get_file_content.return_value = expected_content


    result = await processor._search(data, pattern)


    assert result == expected_content
    mock_github_client.get_file_content.assert_called_once_with(
        "owner/repo", "path/to/file.txt", "main"
    )

@pytest.mark.asyncio
async def test_file_entity_processor_no_repo_path(mock_github_client, mock_context):
    processor = FileEntityProcessor(context=mock_context)
    data = {}  # No repository path
    pattern = f"{FILE_PROPERTY_PREFIX}path/to/file.txt"

    with pytest.raises(ValueError, match="No repository path found in data"):
        await processor._search(data, pattern)

@pytest.mark.asyncio
async def test_file_entity_processor_repo_in_nested_data(mock_github_client, mock_context):
    processor = FileEntityProcessor(context=mock_context)
    data = {
        "repository": {
            "full_name": "owner/repo",
            "default_branch": "develop"
        }
    }
    pattern = f"{FILE_PROPERTY_PREFIX}path/to/file.txt"
    expected_content = "test content"

    mock_github_client.get_file_content.return_value = expected_content


    result = await processor._search(data, pattern)


    assert result == expected_content
    mock_github_client.get_file_content.assert_called_once_with(
        "owner/repo", "path/to/file.txt", "develop"
    )

@pytest.mark.asyncio
async def test_search_entity_processor_success(mock_github_client, mock_context):
    processor = SearchEntityProcessor(context=mock_context)
    data = {
        "full_name": "owner/repo"
    }
    pattern = f"{SEARCH_PROPERTY_PREFIX}path=src/main.py && query=test"
    expected_result = True

    mock_github_client.file_exists.return_value = expected_result


    result = await processor._search(data, pattern)

    assert result == expected_result
    mock_github_client.file_exists.assert_called_once_with(
        "owner/repo", "src/main.py"
    )

@pytest.mark.asyncio
async def test_search_entity_processor_no_repo_path(mock_github_client, mock_context):
    processor = SearchEntityProcessor(context=mock_context)
    data = {}  # No repository path
    pattern = f"{SEARCH_PROPERTY_PREFIX}path=src/main.py && query=test"

    with pytest.raises(ValueError, match="No repository path found in data"):
        await processor._search(data, pattern)

@pytest.mark.asyncio
async def test_search_entity_processor_no_path_component(mock_github_client, mock_context):
    processor = SearchEntityProcessor(context=mock_context)
    data = {
        "full_name": "owner/repo"
    }
    pattern = f"{SEARCH_PROPERTY_PREFIX}query=test"  # Missing path component

    with pytest.raises(ValueError, match="Search string must include a 'path=' component"):
        await processor._search(data, pattern)

@pytest.mark.asyncio
async def test_search_entity_processor_repo_in_nested_data(mock_github_client, mock_context):
    processor = SearchEntityProcessor(context=mock_context)
    data = {
        "repository": {
            "full_name": "owner/repo"
        }
    }
    pattern = f"{SEARCH_PROPERTY_PREFIX}path=src/main.py && query=test"
    expected_result = True

    mock_github_client.file_exists.return_value = expected_result


    result = await processor._search(data, pattern)

    assert result == expected_result
    mock_github_client.file_exists.assert_called_once_with(
        "owner/repo", "src/main.py"
    )
