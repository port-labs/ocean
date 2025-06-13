"""Pytest configuration for Spacelift integration tests."""

import os
import sys
from pathlib import Path

import pytest

# Add the spacelift directory to the Python path so imports work correctly
spacelift_dir = Path(__file__).parent.parent
sys.path.insert(0, str(spacelift_dir))

# Set up test environment variables
os.environ.setdefault("SPACELIFT_API_ENDPOINT", "https://test.app.spacelift.io/graphql")
os.environ.setdefault("SPACELIFT_API_KEY_ID", "test-key-id")
os.environ.setdefault("SPACELIFT_API_KEY_SECRET", "test-secret")
os.environ.setdefault("SPACELIFT_ACCOUNT_NAME", "test-account")
os.environ.setdefault("SPACELIFT_MAX_RETRIES", "2")


@pytest.fixture(autouse=True)
def reset_imports():
    """Reset imports between tests to avoid module caching issues."""
    import sys

    # Store modules to remove after test
    modules_to_remove = [
        name for name in sys.modules.keys() if name.startswith(("main", "spacelift"))
    ]

    yield

    # Clean up imported modules
    for module_name in modules_to_remove:
        if module_name in sys.modules:
            del sys.modules[module_name]


@pytest.fixture
def sample_space():
    """Sample space data for testing."""
    return {
        "id": "space-123",
        "name": "Test Space",
        "description": "A test space",
        "labels": ["test", "example"],
        "createdAt": 1609459200,
        "parentSpace": "parent-space-456",
    }


@pytest.fixture
def sample_stack():
    """Sample stack data for testing."""
    return {
        "id": "stack-456",
        "name": "Test Stack",
        "space": "space-123",
        "administrative": False,
        "state": "FINISHED",
        "description": "A test stack",
        "repository": "test-repo",
        "repositoryURL": "https://github.com/test/repo",
        "provider": "TERRAFORM",
        "labels": ["terraform", "test"],
        "branch": "main",
        "namespace": "test-namespace",
        "createdAt": 1609459200,
        "trackedRuns": [
            {
                "id": "run-789",
                "state": "FINISHED",
                "createdAt": 1609459260,
                "updatedAt": 1609459320,
                "triggeredBy": "user@example.com",
            }
        ],
    }


@pytest.fixture
def sample_run():
    """Sample run (deployment) data for testing."""
    return {
        "id": "run-789",
        "type": "TRACKED",
        "state": "FINISHED",
        "createdAt": 1609459260,
        "updatedAt": 1609459320,
        "triggeredBy": "user@example.com",
        "branch": "main",
        "commit": {
            "hash": "abc123def456",
            "message": "Test commit",
            "authorName": "Test Author",
            "timestamp": 1609459200,
        },
        "driftDetection": False,
        "stack": {"id": "stack-456", "name": "Test Stack"},
    }


@pytest.fixture
def sample_policy():
    """Sample policy data for testing."""
    return {
        "id": "policy-101",
        "name": "Test Policy",
        "type": "ACCESS",
        "space": "space-123",
        "body": "package spacelift\n\nallow { input.user.admin }",
        "createdAt": 1609459200,
        "updatedAt": 1609459260,
        "labels": ["security", "access"],
    }


@pytest.fixture
def sample_user():
    """Sample user data for testing."""
    return {
        "id": "user-202",
        "username": "testuser",
        "name": "Test User",
        "email": "test@example.com",
        "isAdmin": False,
        "isSuspended": False,
        "createdAt": 1609459200,
        "lastSeenAt": 1609459800,
    }
