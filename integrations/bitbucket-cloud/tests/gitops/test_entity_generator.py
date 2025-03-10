import pytest
from typing import AsyncGenerator, Any
from bitbucket_integration.gitops.entity_generator import get_commit_hash_from_payload


@pytest.mark.asyncio
async def test_get_commit_hash_from_payload_single_change():
    """Test extracting commit hashes from payload with a single change."""
    payload = {
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
async def test_get_commit_hash_from_payload_multiple_changes():
    """Test extracting commit hashes from payload with multiple changes."""
    payload = {
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
async def test_get_commit_hash_from_payload_empty_changes():
    """Test handling payload with empty changes."""
    payload = {"push": {"changes": []}}

    result = []
    async for new_hash, old_hash, branch in get_commit_hash_from_payload(payload):
        result.append((new_hash, old_hash, branch))

    assert not result


@pytest.mark.asyncio
async def test_get_commit_hash_from_payload_invalid_payload():
    """Test handling invalid payload structure."""
    payload = {"push": {}}  # Missing changes key

    result = []
    async for new_hash, old_hash, branch in get_commit_hash_from_payload(payload):
        result.append((new_hash, old_hash, branch))

    assert not result
