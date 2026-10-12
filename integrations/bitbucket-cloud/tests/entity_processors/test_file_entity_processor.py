import httpx
import pytest
from unittest.mock import patch, AsyncMock
from bitbucket_cloud.entity_processors.file_entity_processor import FileEntityProcessor

MOCK_PORT_OCEAN_CONTEXT = AsyncMock()


@pytest.mark.asyncio
async def test_file_entity_processor_search_json_success() -> None:
    data = {
        "repo": {"name": "test-repo", "mainbranch": {"name": "develop"}},
        "folder": {"path": "src", "commit": {"hash": "commit-hash"}},
    }
    pattern = "file://config.json"
    expected_content = '{"key": "value"}'

    mock_client = AsyncMock()
    mock_client.get_repository_files.return_value = expected_content

    with patch(
        "bitbucket_cloud.entity_processors.file_entity_processor.init_client",
        return_value=mock_client,
    ):
        processor = FileEntityProcessor(
            context=MOCK_PORT_OCEAN_CONTEXT
        )  # if context isn't used, passing None is fine
        result = await processor._search(data, pattern)
        assert result == expected_content
        mock_client.get_repository_files.assert_called_once_with(
            "test-repo", "commit-hash", "src/config.json"
        )


@pytest.mark.asyncio
async def test_file_entity_processor_search_non_json_success() -> None:
    data = {
        "repo": {"name": "test-repo", "mainbranch": {"name": "main"}},
        "folder": {"path": "docs", "commit": {"hash": "commit123"}},
    }
    pattern = "file://README.md"
    expected_content = "plain text content"

    mock_client = AsyncMock()
    mock_client.get_repository_files.return_value = expected_content

    with patch(
        "bitbucket_cloud.entity_processors.file_entity_processor.init_client",
        return_value=mock_client,
    ):
        processor = FileEntityProcessor(context=MOCK_PORT_OCEAN_CONTEXT)
        result = await processor._search(data, pattern)
        assert result == expected_content
        mock_client.get_repository_files.assert_called_once_with(
            "test-repo", "commit123", "docs/README.md"
        )


@pytest.mark.asyncio
async def test_file_entity_processor_search_error_handling() -> None:
    data = {
        "repo": {"name": "test-repo", "mainbranch": {"name": "main"}},
        "folder": {"path": "configs", "commit": {"hash": "hash123"}},
    }
    pattern = "file://config.json"

    mock_client = AsyncMock()
    mock_client.get_repository_files.side_effect = httpx.ConnectError("boom")

    with patch(
        "bitbucket_cloud.entity_processors.file_entity_processor.init_client",
        return_value=mock_client,
    ):
        processor = FileEntityProcessor(context=MOCK_PORT_OCEAN_CONTEXT)
        result = await processor._search(data, pattern)
        assert result is None


@pytest.mark.asyncio
async def test_file_entity_processor_lets_an_unexpected_error_through() -> None:
    """Only a request failure resolves to null; a bug is not swallowed."""
    data = {
        "repo": {"name": "test-repo", "mainbranch": {"name": "main"}},
        "folder": {"path": "configs", "commit": {"hash": "hash123"}},
    }

    mock_client = AsyncMock()
    mock_client.get_repository_files.side_effect = KeyError("mainbranch")

    with patch(
        "bitbucket_cloud.entity_processors.file_entity_processor.init_client",
        return_value=mock_client,
    ):
        processor = FileEntityProcessor(context=MOCK_PORT_OCEAN_CONTEXT)
        with pytest.raises(KeyError):
            await processor._search(data, "file://config.json")


@pytest.mark.asyncio
async def test_file_entity_processor_search_missing_repo() -> None:
    # Data without repo slug
    data = {
        "repo": {},
        "folder": {"path": "src", "commit": {"hash": "hash123"}},
    }
    pattern = "file://config.json"

    processor = FileEntityProcessor(context=MOCK_PORT_OCEAN_CONTEXT)
    result = await processor._search(data, pattern)
    # Should return None since no repository slug is found
    assert result is None


@pytest.mark.asyncio
async def test_file_entity_processor_search_missing_folder_commit() -> None:
    # Data without folder commit info
    data = {
        "repo": {"name": "test-repo", "mainbranch": {"name": "main"}},
        "folder": {"path": "src"},
    }
    pattern = "file://config.json"
    expected_content = '{"key": "value"}'

    mock_client = AsyncMock()
    mock_client.get_repository_files.return_value = expected_content

    with patch(
        "bitbucket_cloud.entity_processors.file_entity_processor.init_client",
        return_value=mock_client,
    ):
        processor = FileEntityProcessor(context=MOCK_PORT_OCEAN_CONTEXT)
        result = await processor._search(data, pattern)
        # In this case, since commit hash is missing, it should use the default branch ("main")
        assert result == expected_content
        mock_client.get_repository_files.assert_called_once_with(
            "test-repo", "main", "src/config.json"
        )


@pytest.mark.asyncio
async def test_file_entity_processor_prefers_the_slug_over_the_display_name() -> None:
    """The walk emits the full repository object, whose slug is authoritative.

    Hyphenating the display name guesses at the slug and gets it wrong for any name
    Bitbucket does not slugify that way.
    """
    data = {
        "repo": {"slug": "my-repo", "name": "My Repo!", "mainbranch": {"name": "main"}}
    }

    mock_client = AsyncMock()
    mock_client.get_repository_files.return_value = "content"

    with patch(
        "bitbucket_cloud.entity_processors.file_entity_processor.init_client",
        return_value=mock_client,
    ):
        processor = FileEntityProcessor(context=MOCK_PORT_OCEAN_CONTEXT)
        await processor._search(data, "file://port.yml")

    mock_client.get_repository_files.assert_called_once_with(
        "my-repo", "main", "port.yml"
    )


@pytest.mark.asyncio
async def test_file_entity_processor_prefers_the_branch_on_the_emitted_data() -> None:
    """The resync, the folder walk and a push all emit `branch`; mainbranch is the fallback."""
    data = {
        "branch": "develop",
        "repo": {"slug": "my-repo", "mainbranch": {"name": "master"}},
    }

    mock_client = AsyncMock()
    mock_client.get_repository_files.return_value = "content"

    with patch(
        "bitbucket_cloud.entity_processors.file_entity_processor.init_client",
        return_value=mock_client,
    ):
        processor = FileEntityProcessor(context=MOCK_PORT_OCEAN_CONTEXT)
        await processor._search(data, "file://port.yml")

    mock_client.get_repository_files.assert_called_once_with(
        "my-repo", "develop", "port.yml"
    )


@pytest.mark.asyncio
async def test_the_monorepo_path_refuses_to_fetch_without_a_ref() -> None:
    """A folder with no commit hash and no branch anywhere must not request ref=None."""
    data = {"folder": {"path": "src"}, "repo": {"slug": "my-repo"}}

    mock_client = AsyncMock()

    with patch(
        "bitbucket_cloud.entity_processors.file_entity_processor.init_client",
        return_value=mock_client,
    ):
        processor = FileEntityProcessor(context=MOCK_PORT_OCEAN_CONTEXT)
        result = await processor._search(data, "file://port.yml")

    assert result is None
    mock_client.get_repository_files.assert_not_called()


@pytest.mark.asyncio
async def test_the_monorepo_path_prefers_the_folder_commit() -> None:
    """The folder's own commit is the ref when it has one, branch only as the fallback."""
    data = {
        "folder": {"path": "src", "commit": {"hash": "abc123"}},
        "branch": "develop",
        "repo": {"slug": "my-repo"},
    }

    mock_client = AsyncMock()
    mock_client.get_repository_files.return_value = "content"

    with patch(
        "bitbucket_cloud.entity_processors.file_entity_processor.init_client",
        return_value=mock_client,
    ):
        processor = FileEntityProcessor(context=MOCK_PORT_OCEAN_CONTEXT)
        await processor._search(data, "file://port.yml")

    mock_client.get_repository_files.assert_called_once_with(
        "my-repo", "abc123", "src/port.yml"
    )
