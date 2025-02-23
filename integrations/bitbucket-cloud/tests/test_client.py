import pytest
import respx
import httpx

from bitbucket_integration.client import BitbucketClient, BITBUCKET_EVENTS
from port_ocean.context.ocean import ocean

# Fixture to override ocean.integration_config with test values.
@pytest.fixture(autouse=True)
def test_config():
    ocean.integration_config = {
        "bitbucket_base_url": "https://api.test.bitbucket.org/2.0",
        "bitbucket_token": "test_token",
        "bitbucket_workspace": "test_workspace",
    }
    return ocean.integration_config


@pytest.mark.asyncio
async def test_fetch_paginated_data_single_page():
    client = BitbucketClient(
        workspace=ocean.integration_config["bitbucket_workspace"],
        token=ocean.integration_config["bitbucket_token"],
    )
    endpoint = "repositories/test_workspace"
    # Dummy JSON response simulating a single-page result.
    data = {
        "values": [{"id": 1, "name": "repo1"}, {"id": 2, "name": "repo2"}],
        "next": None,
    }

    with respx.mock(base_url=ocean.integration_config["bitbucket_base_url"]) as mock:
        route = mock.get(f"/{endpoint}").respond(json=data)
        result = await client._fetch_paginated_data(endpoint)
        assert result == data["values"]
        assert route.called


@pytest.mark.asyncio
async def test_fetch_paginated_data_multiple_pages():
    client = BitbucketClient(
        workspace=ocean.integration_config["bitbucket_workspace"],
        token=ocean.integration_config["bitbucket_token"],
    )
    endpoint = "repositories/test_workspace"
    first_page = {
        "values": [{"id": 1, "name": "repo1"}],
        "next": f"{ocean.integration_config['bitbucket_base_url']}/{endpoint}?page=2",
    }
    second_page = {
        "values": [{"id": 2, "name": "repo2"}],
        "next": None,
    }

    with respx.mock(base_url=ocean.integration_config["bitbucket_base_url"]) as mock:
        route1 = mock.get(f"/{endpoint}").respond(json=first_page)
        route2 = mock.get(f"/{endpoint}?page=2").respond(json=second_page)
        result = await client._fetch_paginated_data(endpoint)
        expected = first_page["values"] + second_page["values"]
        assert result == expected
        assert route1.called
        assert route2.called


@pytest.mark.asyncio
async def test_fetch_repositories():
    client = BitbucketClient(
        workspace=ocean.integration_config["bitbucket_workspace"],
        token=ocean.integration_config["bitbucket_token"],
    )
    endpoint = f"repositories/{ocean.integration_config['bitbucket_workspace']}"
    data = {
        "values": [{"id": 1, "name": "repo1"}],
        "next": None,
    }

    with respx.mock(base_url=ocean.integration_config["bitbucket_base_url"]) as mock:
        route = mock.get(f"/{endpoint}").respond(json=data)
        repos = await client.fetch_repositories()
        assert repos == data["values"]
        assert route.called


@pytest.mark.asyncio
async def test_fetch_projects():
    client = BitbucketClient(
        workspace=ocean.integration_config["bitbucket_workspace"],
        token=ocean.integration_config["bitbucket_token"],
    )
    endpoint = f"workspaces/{ocean.integration_config['bitbucket_workspace']}/projects"
    data = {
        "values": [{"id": "proj1", "name": "Project 1"}],
        "next": None,
    }

    with respx.mock(base_url=ocean.integration_config["bitbucket_base_url"]) as mock:
        route = mock.get(f"/{endpoint}").respond(json=data)
        projects = await client.fetch_projects()
        assert projects == data["values"]
        assert route.called


@pytest.mark.asyncio
async def test_fetch_pull_requests():
    client = BitbucketClient(
        workspace=ocean.integration_config["bitbucket_workspace"],
        token=ocean.integration_config["bitbucket_token"],
    )
    repo_slug = "test_repo"
    endpoint = f"repositories/{ocean.integration_config['bitbucket_workspace']}/{repo_slug}/pullrequests"
    data = {
        "values": [{"id": 101, "title": "PR1"}],
        "next": None,
    }

    with respx.mock(base_url=ocean.integration_config["bitbucket_base_url"]) as mock:
        route = mock.get(f"/{endpoint}").respond(json=data)
        prs = await client.fetch_pull_requests(repo_slug)
        assert prs == data["values"]
        assert route.called


@pytest.mark.asyncio
async def test_fetch_components():
    client = BitbucketClient(
        workspace=ocean.integration_config["bitbucket_workspace"],
        token=ocean.integration_config["bitbucket_token"],
    )
    repo_slug = "test_repo"
    endpoint = f"repositories/{ocean.integration_config['bitbucket_workspace']}/{repo_slug}/components"
    data = {
        "values": [{"id": "comp1", "name": "Component1"}],
        "next": None,
    }

    with respx.mock(base_url=ocean.integration_config["bitbucket_base_url"]) as mock:
        route = mock.get(f"/{endpoint}").respond(json=data)
        components = await client.fetch_components(repo_slug)
        assert components == data["values"]
        assert route.called


@pytest.mark.asyncio
async def test_register_webhook():
    client = BitbucketClient(
        workspace=ocean.integration_config["bitbucket_workspace"],
        token=ocean.integration_config["bitbucket_token"],
    )
    webhook_url = "https://test.com/webhook"
    secret = "testsecret"
    endpoint = f"/repositories/{ocean.integration_config['bitbucket_workspace']}/hooks"
    payload = {
        "description": "Port Ocean Integration Webhook",
        "url": webhook_url,
        "active": True,
        "events": BITBUCKET_EVENTS,
        "secret": secret,
    }
    response_json = {"id": "webhook123", "url": webhook_url}

    with respx.mock(base_url=ocean.integration_config["bitbucket_base_url"]) as mock:
        route = mock.post(
            endpoint,
            json=payload,
            headers={"Authorization": f"Bearer {ocean.integration_config['bitbucket_token']}"}
        ).respond(json=response_json)
        await client.register_webhook(webhook_url, secret)
        assert route.called
