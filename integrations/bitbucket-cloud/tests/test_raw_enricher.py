import httpx
import pytest
from unittest.mock import patch, AsyncMock
from bitbucket_cloud.raw_enricher import BitbucketRawEnricher

MOCK_PORT_OCEAN_CONTEXT = AsyncMock()


@pytest.mark.asyncio
async def test_resolve_file_ref_json_success() -> None:
    data = {
        "repo": {"name": "test-repo", "mainbranch": {"name": "develop"}},
        "folder": {"path": "src", "commit": {"hash": "commit-hash"}},
    }
    path = "config.json"
    expected_content = '{"key": "value"}'

    mock_client = AsyncMock()
    mock_client.get_repository_files.return_value = expected_content

    with patch(
        "bitbucket_cloud.raw_enricher.init_client",
        return_value=mock_client,
    ):
        enricher = BitbucketRawEnricher(context=MOCK_PORT_OCEAN_CONTEXT)
        result = await enricher.resolve_file_ref(data, path)
        assert result == expected_content
        mock_client.get_repository_files.assert_called_once_with(
            "test-repo", "commit-hash", "src/config.json"
        )


@pytest.mark.asyncio
async def test_resolve_file_ref_non_json_success() -> None:
    data = {
        "repo": {"name": "test-repo", "mainbranch": {"name": "main"}},
        "folder": {"path": "docs", "commit": {"hash": "commit123"}},
    }
    path = "README.md"
    expected_content = "plain text content"

    mock_client = AsyncMock()
    mock_client.get_repository_files.return_value = expected_content

    with patch(
        "bitbucket_cloud.raw_enricher.init_client",
        return_value=mock_client,
    ):
        enricher = BitbucketRawEnricher(context=MOCK_PORT_OCEAN_CONTEXT)
        result = await enricher.resolve_file_ref(data, path)
        assert result == expected_content
        mock_client.get_repository_files.assert_called_once_with(
            "test-repo", "commit123", "docs/README.md"
        )


@pytest.mark.asyncio
async def test_resolve_file_ref_error_handling() -> None:
    data = {
        "repo": {"name": "test-repo", "mainbranch": {"name": "main"}},
        "folder": {"path": "configs", "commit": {"hash": "hash123"}},
    }
    path = "config.json"

    mock_client = AsyncMock()
    mock_client.get_repository_files.side_effect = httpx.ConnectError("boom")

    with patch(
        "bitbucket_cloud.raw_enricher.init_client",
        return_value=mock_client,
    ):
        enricher = BitbucketRawEnricher(context=MOCK_PORT_OCEAN_CONTEXT)
        result = await enricher.resolve_file_ref(data, path)
        assert result is None


@pytest.mark.asyncio
async def test_resolve_file_ref_lets_an_unexpected_error_through() -> None:
    """Only a request failure resolves to null; a bug is not swallowed."""
    data = {
        "repo": {"name": "test-repo", "mainbranch": {"name": "main"}},
        "folder": {"path": "configs", "commit": {"hash": "hash123"}},
    }

    mock_client = AsyncMock()
    mock_client.get_repository_files.side_effect = KeyError("mainbranch")

    with patch(
        "bitbucket_cloud.raw_enricher.init_client",
        return_value=mock_client,
    ):
        enricher = BitbucketRawEnricher(context=MOCK_PORT_OCEAN_CONTEXT)
        with pytest.raises(KeyError):
            await enricher.resolve_file_ref(data, "config.json")


@pytest.mark.asyncio
async def test_resolve_file_ref_missing_repo() -> None:
    # Data without repo slug
    data = {
        "repo": {},
        "folder": {"path": "src", "commit": {"hash": "hash123"}},
    }
    path = "config.json"

    enricher = BitbucketRawEnricher(context=MOCK_PORT_OCEAN_CONTEXT)
    result = await enricher.resolve_file_ref(data, path)
    # Should return None since no repository slug is found
    assert result is None


@pytest.mark.asyncio
async def test_resolve_file_ref_missing_folder_commit() -> None:
    # Data without folder commit info
    data = {
        "repo": {"name": "test-repo", "mainbranch": {"name": "main"}},
        "folder": {"path": "src"},
    }
    path = "config.json"
    expected_content = '{"key": "value"}'

    mock_client = AsyncMock()
    mock_client.get_repository_files.return_value = expected_content

    with patch(
        "bitbucket_cloud.raw_enricher.init_client",
        return_value=mock_client,
    ):
        enricher = BitbucketRawEnricher(context=MOCK_PORT_OCEAN_CONTEXT)
        result = await enricher.resolve_file_ref(data, path)
        # In this case, since commit hash is missing, it should use the default branch ("main")
        assert result == expected_content
        mock_client.get_repository_files.assert_called_once_with(
            "test-repo", "main", "src/config.json"
        )
