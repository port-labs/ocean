import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from typing import Dict, Any, List, AsyncGenerator

from bitbucket_cloud.helpers.file_kind_live_event import (
    extract_hash_from_payload,
    determine_action,
    check_single_path,
    check_and_load_file_prefix,
    process_file_changes,
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

    # Test wildcard match
    assert check_single_path("path/to/test.txt", ["*.txt"], "path/to")

    # Test no match
    assert not check_single_path("path/to/test.txt", ["other.txt"], "path/to")

    # Test empty filenames list (should match any filename)
    assert check_single_path("path/to/test.txt", [], "path/to")

    # Test empty config path (should match any path)
    assert check_single_path("path/to/test.txt", ["test.txt"], "")

    # Test root directory file with root path
    assert check_single_path("README.md", ["README.md"], "/")

    # Test root directory file with empty path
    assert check_single_path("README.md", ["README.md"], "")


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
async def test_process_file_changes() -> None:
    """Test the process_file_changes function."""
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
    mock_webhook_client.get_repository_files.return_value = [{"test": "test content"}]

    # Mock selector
    mock_selector = MagicMock()
    mock_selector.files.filenames = ["*.txt"]
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
    mock_selector.files.filenames = ["*.yaml"]

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
