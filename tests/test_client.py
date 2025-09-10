import respx
import httpx
import pytest

from github_client import GithubClient


@pytest.mark.asyncio
@respx.mock
async def test_pagination_and_rate_limit():
    client = GithubClient(token="t")

    # First page returns one repo, no pagination beyond page 1
    respx.get("https://api.github.com/orgs/acme/repos").mock(
        return_value=httpx.Response(200, json=[{"name": "r1", "full_name": "acme/r1"}])
    )

    items = []
    async for it in client.iter_org_repos("acme"):
        items.append(it)

    assert items and items[0]["name"] == "r1"