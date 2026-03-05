"""Shared pytest fixtures for the Vercel integration test suite."""

from __future__ import annotations

from typing import Any

import pytest


@pytest.fixture
def vercel_token() -> str:
    return "test_token_abc123"


@pytest.fixture
def team_id() -> str:
    return "team_xyz789"


@pytest.fixture
def sample_team() -> dict[str, Any]:
    return {
        "id": "team_xyz789",
        "slug": "acme",
        "name": "Acme Corp",
        "avatar": "https://vercel.com/api/www/avatar/acme",
        "createdAt": 1700000000000,
        "membership": {"role": "OWNER"},
    }


@pytest.fixture
def sample_project() -> dict[str, Any]:
    return {
        "id": "prj_abc123",
        "name": "my-nextjs-app",
        "framework": "nextjs",
        "nodeVersion": "20.x",
        "createdAt": 1700000000000,
        "updatedAt": 1700010000000,
        "teamId": "team_xyz789",
        "latestDeployments": [{"url": "my-nextjs-app-git-main-acme.vercel.app"}],
    }


@pytest.fixture
def sample_deployment() -> dict[str, Any]:
    return {
        "uid": "dpl_def456",
        "name": "my-nextjs-app",
        "url": "my-nextjs-app-abc123-acme.vercel.app",
        "state": "READY",
        "target": "production",
        "createdAt": 1700005000000,
        "buildingAt": 1700005100000,
        "ready": 1700005500000,
        "source": "git",
        "creator": {"uid": "usr_001", "username": "alice"},
        "meta": {
            "githubCommitSha": "abc123def456",
            "githubCommitMessage": "feat: add dark mode",
            "githubCommitRef": "main",
        },
    }


@pytest.fixture
def sample_domain() -> dict[str, Any]:
    return {
        "name": "app.example.com",
        "apexName": "example.com",
        "projectId": "prj_abc123",
        "verified": True,
        "gitBranch": "main",
        "redirect": None,
        "createdAt": 1700000000000,
        "updatedAt": 1700001000000,
    }
