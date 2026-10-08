import pytest
from loguru import logger
from unittest.mock import AsyncMock, MagicMock, patch
from typing import Dict, Any, List, AsyncGenerator

from bitbucket_cloud.helpers.utils import matches_configured_file
from bitbucket_cloud.helpers.file_kind_live_event import (
    extract_hash_from_payload,
    determine_action,
    check_single_path,
    check_and_load_file_prefix,
    process_file_changes,
    process_file_value,
)

# Test data
SAMPLE_CHANGE: Dict[str, Dict[str, Any]] = {
    "new": {"target": {"hash": "new_hash"}, "name": "main"},
    "old": {"target": {"hash": "old_hash"}},
}

SAMPLE_DIFF_STAT: Dict[str, Any] = {
    "new": {"path": "new/path/file.txt"},
    "old": {"path": "old/path/file.txt"},
    "status": "modified",
    "lines_added": 10,
    "lines_removed": 5,
    "commit": {"hash": "new_hash"},
}


@pytest.mark.asyncio
async def test_extract_hash_from_payload() -> None:
    """Test the extract_hash_from_payload function."""
    new_hash, old_hash, branch = extract_hash_from_payload(SAMPLE_CHANGE)
    assert new_hash == "new_hash"
    assert old_hash == "old_hash"
    assert branch == "main"


@pytest.mark.asyncio
async def test_determine_action() -> None:
    """Test the determine_action function with different scenarios."""
    # Test added file
    diff_stat_added: Dict[str, Any] = {
        "new": {"path": "new/path/file.txt"},
        "old": {},
    }
    is_added, is_modified, is_deleted = determine_action(diff_stat_added)
    assert is_added is True
    assert is_modified is False
    assert is_deleted is False

    # Test deleted file
    diff_stat_deleted: Dict[str, Any] = {
        "new": {},
        "old": {"path": "old/path/file.txt"},
    }
    is_added, is_modified, is_deleted = determine_action(diff_stat_deleted)
    assert is_added is False
    assert is_modified is False
    assert is_deleted is True

    # Test modified file
    is_added, is_modified, is_deleted = determine_action(SAMPLE_DIFF_STAT)
    assert is_added is False
    assert is_modified is True
    assert is_deleted is False


@pytest.mark.asyncio
async def test_check_single_path() -> None:
    """Test the check_single_path function with various scenarios."""
    # Test exact filename match
    assert check_single_path("path/to/test.txt", ["test.txt"], "path/to")

    # Wildcards are not supported, and never were on the resync walk
    assert not check_single_path("path/to/test.txt", ["*.txt"], "path/to")

    # Test no match
    assert not check_single_path("path/to/test.txt", ["other.txt"], "path/to")

    # No filenames means no files, as the selector documents and the walk behaves
    assert not check_single_path("path/to/test.txt", [], "path/to")

    # A suffix lookalike is not a match
    assert not check_single_path("path/to/airport.yml", ["port.yml"], "path/to")

    # A configured value carrying directories matches at the boundary
    assert check_single_path("a/conf/README.md", ["conf/README.md"], "a")

    # Test empty config path (should match any path)
    assert check_single_path("path/to/test.txt", ["test.txt"], "")

    # Test root directory file with root path
    assert check_single_path("README.md", ["README.md"], "/")

    # Test root directory file with empty path
    assert check_single_path("README.md", ["README.md"], "")

    # Leading/trailing slashes on config path are equivalent
    for config_path in ("hello/test", "/hello/test", "/hello/test/", "hello/test/"):
        assert check_single_path("hello/test/file.txt", ["file.txt"], config_path)
        assert not check_single_path("hello/other/file.txt", ["file.txt"], config_path)


@pytest.mark.asyncio
async def test_check_and_load_file_prefix() -> None:
    """Test the check_and_load_file_prefix function."""
    # Mock the init_client function
    with patch("bitbucket_cloud.helpers.file_kind_live_event.init_client") as mock_init:
        mock_client = AsyncMock()
        mock_init.return_value = mock_client

        # Test with dictionary data
        test_data: Dict[str, str] = {"key": "value"}
        result = await check_and_load_file_prefix(
            test_data,
            "test/path",
            "test-repo",
            "test-hash",
            {"commit": {"hash": "test-hash"}},
            {"name": "test-repo"},
            "main",
        )
        assert result["content"] == {"key": "value"}
        assert result["metadata"] == {"commit": {"hash": "test-hash"}}
        assert result["repo"] == {"name": "test-repo"}
        assert result["branch"] == "main"

        # Test with list data
        test_list: List[Dict[str, str]] = [{"key": "value"}]
        result = await check_and_load_file_prefix(
            test_list,
            "test/path",
            "test-repo",
            "test-hash",
            {"commit": {"hash": "test-hash"}},
            {"name": "test-repo"},
            "main",
        )
        assert result["content"] == [{"key": "value"}]
        assert result["metadata"] == {"commit": {"hash": "test-hash"}}
        assert result["repo"] == {"name": "test-repo"}
        assert result["branch"] == "main"


@pytest.mark.asyncio
async def test_process_file_changes_plain_text_content() -> None:
    """Plain-text files are returned as scalar content without prefix loading."""
    plain_diff_stat: Dict[str, Any] = {
        "new": {"path": ".nvmrc"},
        "old": {"path": ".nvmrc"},
        "status": "modified",
        "commit": {"hash": "new_hash"},
    }

    async def mock_retrieve_diff_stat(
        *args: Any, **kwargs: Any
    ) -> AsyncGenerator[List[Dict[str, Any]], None]:
        yield [plain_diff_stat]

    mock_webhook_client = AsyncMock()
    mock_webhook_client.retrieve_diff_stat = mock_retrieve_diff_stat
    mock_webhook_client.get_repository_files.return_value = "18"

    mock_selector = MagicMock()
    mock_selector.files.filenames = [".nvmrc"]
    mock_selector.files.path = "/"

    with patch("bitbucket_cloud.helpers.file_kind_live_event.init_client") as mock_init:
        mock_init.return_value = AsyncMock()

        updated, deleted = await process_file_changes(
            "test-repo",
            [SAMPLE_CHANGE],
            mock_selector,
            False,
            mock_webhook_client,
            {"repository": {"name": "test-repo"}},
        )

    assert deleted == []
    assert len(updated) == 1
    assert updated[0]["content"] == "18"
    assert updated[0]["metadata"]["path"] == ".nvmrc"
    mock_init.assert_not_called()


@pytest.mark.asyncio
async def test_process_file_changes() -> None:
    """Test the process_file_changes function."""
    # Mock the init_client function
    with patch("bitbucket_cloud.helpers.file_kind_live_event.init_client") as mock_init:
        mock_client = AsyncMock()
        mock_init.return_value = mock_client

        # Mock the webhook client
        mock_webhook_client = AsyncMock()

        # Create an async generator for retrieve_diff_stat
        async def mock_retrieve_diff_stat(
            *args: Any, **kwargs: Any
        ) -> AsyncGenerator[List[Dict[str, Any]], None]:
            # Return a list of diff stats, not a list of lists
            yield [SAMPLE_DIFF_STAT]

        mock_webhook_client.retrieve_diff_stat = mock_retrieve_diff_stat
        # Return a list of dictionaries instead of a string
        mock_webhook_client.get_repository_files.return_value = [
            {"test": "test content"}
        ]

        # Mock selector
        mock_selector = MagicMock()
        mock_selector.files.filenames = ["test.txt"]
        mock_selector.files.path = "*"

        # Test payload
        test_payload: Dict[str, Dict[str, str]] = {"repository": {"name": "test-repo"}}

        # Test with YAML file
        yaml_diff_stat: Dict[str, Any] = SAMPLE_DIFF_STAT.copy()
        yaml_diff_stat["new"]["path"] = "test.yaml"

        # Update the mock to return the YAML diff stat
        async def mock_retrieve_diff_stat_yaml(
            *args: Any, **kwargs: Any
        ) -> AsyncGenerator[List[Dict[str, Any]], None]:
            # Return a list of diff stats, not a list of lists
            yield [yaml_diff_stat]

        mock_webhook_client.retrieve_diff_stat = mock_retrieve_diff_stat_yaml

        # Update the selector to match the YAML file
        mock_selector.files.filenames = ["test.yaml"]

        updated, deleted = await process_file_changes(
            "test-repo",
            [SAMPLE_CHANGE],
            mock_selector,
            False,
            mock_webhook_client,
            test_payload,
        )

        assert len(updated) > 0
        assert len(deleted) == 0
        assert mock_webhook_client.get_repository_files.called


@pytest.mark.asyncio
async def test_push_and_resync_agree_on_the_same_filenames_selector() -> None:
    """One `files` selector, one answer. These disagreed before: the walk matched the
    whole path against a path-boundary suffix, the push handler fnmatched the basename.
    """
    cases = [
        ("port.yml", ["port.yml"], "/"),
        ("charts/app/port.yml", ["port.yml"], "charts/*"),
        ("airport.yml", ["port.yml"], "*/"),
        ("test.yaml", ["*.yaml"], "*"),
        ("a/conf/README.md", ["conf/README.md"], "a"),
        ("port.yml", [], "/"),
    ]
    for file_path, filenames, configured_path in cases:
        assert check_single_path(file_path, filenames, configured_path) is (
            matches_configured_file(file_path, filenames, configured_path)
        ), f"{file_path} / {filenames} / {configured_path}"


@pytest.mark.asyncio
async def test_push_skips_a_file_whose_content_cannot_be_read() -> None:
    """get_repository_files returns None for a file Bitbucket does not have. Upserting
    it would replace a good entity in Port with one whose content is null."""
    diff_stat: Dict[str, Any] = {
        "new": {"path": ".nvmrc"},
        "old": {"path": ".nvmrc"},
        "status": "modified",
        "commit": {"hash": "new_hash"},
    }

    async def mock_retrieve_diff_stat(
        *args: Any, **kwargs: Any
    ) -> AsyncGenerator[List[Dict[str, Any]], None]:
        yield [diff_stat]

    mock_webhook_client = AsyncMock()
    mock_webhook_client.retrieve_diff_stat = mock_retrieve_diff_stat
    mock_webhook_client.get_repository_files.return_value = None

    mock_selector = MagicMock()
    mock_selector.files.filenames = [".nvmrc"]
    mock_selector.files.path = "/"

    with patch("bitbucket_cloud.helpers.file_kind_live_event.init_client") as mock_init:
        mock_init.return_value = AsyncMock()
        updated, deleted = await process_file_changes(
            "test-repo",
            [SAMPLE_CHANGE],
            mock_selector,
            False,
            mock_webhook_client,
            {"repository": {"name": "test-repo"}},
        )

    assert updated == []
    assert deleted == []


@pytest.mark.asyncio
async def test_nested_file_reference_resolves_to_null_when_unreadable() -> None:
    """A file:// value inside a parsed file, on both the walk and the push path.

    Without the None guard the missing file reaches parse_file, which reports it as
    "Error parsing file" - an error about the wrong thing, naming neither the file nor
    the repository.
    """
    records: list[tuple[str, str]] = []
    sink_id = logger.add(
        lambda record: records.append(
            (record.record["level"].name, record.record["message"])
        ),
        level="WARNING",
    )
    client = AsyncMock()
    client.get_repository_files.return_value = None
    try:
        result = await process_file_value(
            "file://missing.json", "conf", "test-repo", "abc123def456", client
        )
    finally:
        logger.remove(sink_id)

    assert result is None
    assert [level for level, _ in records] == ["WARNING"]
    assert "conf/missing.json" in records[0][1]
    assert "test-repo" in records[0][1]
