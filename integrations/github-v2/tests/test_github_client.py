from unittest.mock import AsyncMock, MagicMock

import httpx
import pytest
from port_ocean.context.event import event_context

from client import GitHub
from utils import create_github_client


@pytest.fixture
def github_instance() -> GitHub:
    github = create_github_client()
    return github


def test_github_init(
    github_instance: GitHub,
) -> None:
    assert github_instance._http_client is not None
    assert github_instance._base_url is not None


@pytest.mark.asyncio
async def test_fetching_pageless_respository(github_instance: GitHub) -> None:
    async with event_context("test_event"):
        response = MagicMock(spec=httpx.Response)
        response.status_code = 200
        response.raise_for_status.return_value = MagicMock()
        response.json = MagicMock(return_value=[{id: 12, "name": "test repo"}])
        response.headers = {}
        request = AsyncMock(spec=httpx.Request, return_value=response)
        github_instance._http_client.request = request

        returned_pages = []
        async for page in github_instance.get_repositories("test"):
            returned_pages.append(page)

        assert len(returned_pages) == 1
        github_instance._http_client.request.assert_called_once()


@pytest.mark.asyncio
async def test_fetching_page_respository(github_instance: GitHub) -> None:
    async with event_context("test_event"):
        res_data = [{id: 12, "name": "test repo"}]
        response = MagicMock(spec=httpx.Response)
        response.raise_for_status = MagicMock()
        response.status_code = 200
        response.json = MagicMock(return_value=res_data)
        response.headers = {
            "Link": "<https://api.github.com/repositories/1300192/issues?page=4>; rel='next',"
        }
        github_instance._http_client.request = AsyncMock(return_value=response)

        returned_pages = []
        async for page in github_instance.get_repositories("test"):
            returned_pages.append(page)
            if len(returned_pages) == 2:
                response.headers = {}

        assert len(returned_pages) == 2
        github_instance._http_client.request.assert_called()
        assert github_instance._http_client.request.call_count == 2
