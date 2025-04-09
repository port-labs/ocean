from unittest.mock import AsyncMock, MagicMock
import httpx
import pytest

from github import GitHub


@pytest.fixture
def github_instance() -> GitHub:
    github = GitHub("test_token")
    return github


def test_github_init(github_instance: GitHub) -> None:
    assert github_instance._http_client is not None
    assert github_instance._base_url is not None


@pytest.mark.asyncio
async def test_fetching_pageless_respository(github_instance: GitHub) -> None:
    github_instance._http_client = MagicMock(spec=httpx.Client)
    response = AsyncMock(spec=httpx.Response)
    response.json = MagicMock(return_val=[{id: 12, "name": "test repo"}])
    response.headers = {}
    github_instance._http_client.get = AsyncMock(return_val=response)

    returned_pages = []
    async for page in github_instance.get_repositories("test"):
        returned_pages.append(page)

    assert len(returned_pages) == 1
    github_instance._http_client.get.assert_called_once()


@pytest.mark.asyncio
async def test_fetching_page_respository(github_instance: GitHub) -> None:
    github_instance._http_client = MagicMock(spec=httpx.Client)
    response = AsyncMock(spec=httpx.Response)
    response.json = MagicMock(return_val=[{id: 12, "name": "test repo"}])
    response.headers = {
        "Link": "<https://api.github.com/repositories/1300192/issues?page=4>; rel='next',"
    }
    github_instance._http_client.get = AsyncMock(return_val=response)

    returned_pages = []
    async for page in github_instance.get_repositories("test"):
        returned_pages.append(page)

    assert len(returned_pages) == 2
    github_instance._http_client.get.assert_called_once()
