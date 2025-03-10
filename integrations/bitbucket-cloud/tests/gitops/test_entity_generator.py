import pytest
from typing import Dict, Any
from bitbucket_integration.gitops.entity_generator import get_commit_hash_from_payload


@pytest.mark.asyncio
async def test_get_commit_hash_from_payload_single_change() -> None:
    """Test extracting commit hashes from payload with a single change."""
    payload: Dict[str, Any] = {
        "push": {
            "changes": [
                {
                    "new": {"target": {"hash": "new-hash"}, "name": "test"},
                    "old": {"target": {"hash": "old-hash"}, "name": "test"},
                }
            ]
        }
    }

    result = []
    async for new_hash, old_hash, branch in get_commit_hash_from_payload(payload):
        result.append((new_hash, old_hash, branch))

    assert result == [("new-hash", "old-hash", "test")]


@pytest.mark.asyncio
async def test_get_commit_hash_from_payload_multiple_changes() -> None:
    """Test extracting commit hashes from payload with multiple changes."""
    payload: Dict[str, Any] = {
        "push": {
            "changes": [
                {
                    "new": {"target": {"hash": "new-hash-1"}, "name": "test"},
                    "old": {"target": {"hash": "old-hash-1"}, "name": "test"},
                },
                {
                    "new": {"target": {"hash": "new-hash-2"}, "name": "main"},
                    "old": {"target": {"hash": "old-hash-2"}, "name": "main"},
                },
            ]
        }
    }

    result = []
    async for new_hash, old_hash, branch in get_commit_hash_from_payload(payload):
        result.append((new_hash, old_hash, branch))

    assert result == [
        ("new-hash-1", "old-hash-1", "test"),
        ("new-hash-2", "old-hash-2", "main"),
    ]


@pytest.mark.asyncio
async def test_get_commit_hash_from_payload_empty_changes() -> None:
    """Test handling payload with empty changes."""
    payload: Dict[str, Any] = {"push": {"changes": []}}

    result = []
    async for new_hash, old_hash, branch in get_commit_hash_from_payload(payload):
        result.append((new_hash, old_hash, branch))

    assert not result


@pytest.mark.asyncio
async def test_get_commit_hash_from_payload_invalid_payload() -> None:
    """Test handling invalid payload structure."""
    payload: Dict[str, Any] = {"push": {}}  # Missing changes key

    result = []
    async for new_hash, old_hash, branch in get_commit_hash_from_payload(payload):
        result.append((new_hash, old_hash, branch))

    assert not result
