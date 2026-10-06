from typing import Any, AsyncGenerator, Dict, List
from unittest.mock import AsyncMock, MagicMock, patch

import asyncio
import pytest
from httpx import Response
from port_ocean.context.ocean import initialize_port_ocean_context
from port_ocean.exceptions.context import PortOceanContextAlreadyInitializedError

from azure_devops.client.auth import PatAuthProvider
from azure_devops.client.azure_devops_client import AzureDevopsClient

MOCK_ORG_URL = "https://dev.azure.com/testorg"
MOCK_AUTH_PROVIDER = PatAuthProvider("test_pat")
MOCK_AUTH_USERNAME = "port"


@pytest.fixture(autouse=True)
def mock_ocean_context() -> None:
    try:
        mock_ocean_app = MagicMock()
        mock_ocean_app.config.integration.config = {
            "organization_url": MOCK_ORG_URL,
            "personal_access_token": "test_pat",
        }
        mock_ocean_app.integration_router = MagicMock()
        mock_ocean_app.port_client = MagicMock()
        mock_ocean_app.cache_provider = AsyncMock()
        mock_ocean_app.cache_provider.get.return_value = None
        initialize_port_ocean_context(mock_ocean_app)
    except PortOceanContextAlreadyInitializedError:
        pass


MOCK_PROJECT = {"id": "proj-1", "name": "MyProject"}

MOCK_WIKI_PROJECT = {
    "id": "wiki-uuid-1",
    "name": "MyProject.wiki",
    "type": "projectWiki",
    "projectId": "proj-1",
    "repositoryId": "wiki-uuid-1",
    "mappedPath": "/",
}

MOCK_WIKI_CODE = {
    "id": "wiki-uuid-2",
    "name": "code-docs",
    "type": "codeWiki",
    "projectId": "proj-1",
    "repositoryId": "repo-uuid-1",
    "mappedPath": "/docs",
}

MOCK_PAGES = [
    {"id": 1, "path": "/Home"},
    {"id": 3, "path": "/Architecture"},
    {"id": 4, "path": "/Architecture/API-Gateway"},
    {"id": 5, "path": "/Runbooks"},
]

MOCK_FULL_PAGE = {
    "id": 1,
    "path": "/Home",
    "content": "# Home\n\nWelcome.",
    "gitItemPath": "/Home.md",
    "order": 0,
    "isParentPage": False,
    "subPages": [],
    "url": "https://dev.azure.com/testorg/proj-1/_apis/wiki/wikis/wiki-uuid-1/pages/%2FHome",
    "remoteUrl": "https://dev.azure.com/testorg/proj-1/_wiki/wikis/wiki-uuid-1?pagePath=%2FHome",
}


def _make_client() -> AzureDevopsClient:
    return AzureDevopsClient(MOCK_ORG_URL, MOCK_AUTH_PROVIDER, MOCK_AUTH_USERNAME)


# ── _get_wikis_for_project ─────────────────────────────────────────────


@pytest.mark.asyncio
async def test_get_wikis_for_project_returns_wikis_with_project() -> None:
    client = _make_client()

    with patch.object(client, "send_request") as mock_send:
        mock_send.return_value = Response(
            status_code=200,
            json={"value": [MOCK_WIKI_PROJECT], "count": 1},
        )

        wikis = await client._get_wikis_for_project(MOCK_PROJECT)

        assert len(wikis) == 1
        assert wikis[0]["name"] == "MyProject.wiki"
        assert wikis[0]["__project"] == MOCK_PROJECT
        mock_send.assert_called_once_with(
            "GET",
            f"{MOCK_ORG_URL}/proj-1/_apis/wiki/wikis",
            params={"api-version": "7.1"},
        )


@pytest.mark.asyncio
async def test_get_wikis_for_project_returns_empty_on_404() -> None:
    client = _make_client()

    with patch.object(client, "send_request", return_value=None):
        wikis = await client._get_wikis_for_project(MOCK_PROJECT)

        assert wikis == []


# ── get_wiki_pages_batch ──────────────────────────────────────────────


@pytest.mark.asyncio
async def testget_wiki_pages_batch_single_page() -> None:
    client = _make_client()

    with patch.object(client, "send_request") as mock_send:
        mock_send.return_value = Response(
            status_code=200,
            json={"value": MOCK_PAGES, "count": 4},
        )

        batches: List[List[Dict[str, Any]]] = []
        async for batch in client.get_wiki_pages_batch(
            "proj-1", "wiki-uuid-1", "MyProject.wiki"
        ):
            batches.append(batch)

        assert len(batches) == 1
        assert batches[0] == MOCK_PAGES


@pytest.mark.asyncio
async def testget_wiki_pages_batch_pagination() -> None:
    client = _make_client()

    page1 = [{"id": 1, "path": "/Page1"}, {"id": 2, "path": "/Page2"}]
    page2 = [{"id": 3, "path": "/Page3"}]

    responses = [
        Response(
            status_code=200,
            json={"value": page1, "count": 2},
            headers={"x-ms-continuationtoken": "2"},
        ),
        Response(
            status_code=200,
            json={"value": page2, "count": 1},
        ),
    ]

    with patch.object(client, "send_request", side_effect=responses):
        all_pages: List[Dict[str, Any]] = []
        async for batch in client.get_wiki_pages_batch(
            "proj-1", "wiki-uuid-1", "MyProject.wiki"
        ):
            all_pages.extend(batch)

        assert len(all_pages) == 3
        assert all_pages == page1 + page2


@pytest.mark.asyncio
async def testget_wiki_pages_batch_empty_wiki() -> None:
    client = _make_client()

    with patch.object(client, "send_request") as mock_send:
        mock_send.return_value = Response(
            status_code=200,
            json={"value": [], "count": 0},
        )

        batches: List[List[Dict[str, Any]]] = []
        async for batch in client.get_wiki_pages_batch(
            "proj-1", "wiki-uuid-1", "MyProject.wiki"
        ):
            batches.append(batch)

        assert batches == []


@pytest.mark.asyncio
async def testget_wiki_pages_batch_no_response() -> None:
    client = _make_client()

    with patch.object(client, "send_request", return_value=None):
        batches: List[List[Dict[str, Any]]] = []
        async for batch in client.get_wiki_pages_batch(
            "proj-1", "wiki-uuid-1", "MyProject.wiki"
        ):
            batches.append(batch)

        assert batches == []


# ── _get_wiki_page_by_id ──────────────────────────────────────────────


@pytest.mark.asyncio
async def test_get_wiki_page_by_id_with_content() -> None:
    client = _make_client()

    with patch.object(client, "send_request") as mock_send:
        mock_send.return_value = Response(
            status_code=200,
            json=MOCK_FULL_PAGE,
        )

        page = await client._get_wiki_page_by_id(
            "proj-1", "wiki-uuid-1", "MyProject.wiki", 1, include_content=True
        )

        assert page is not None
        assert page["content"] == "# Home\n\nWelcome."
        mock_send.assert_called_once_with(
            "GET",
            f"{MOCK_ORG_URL}/proj-1/_apis/wiki/wikis/wiki-uuid-1/pages/1",
            params={"api-version": "7.1", "includeContent": "true"},
        )


@pytest.mark.asyncio
async def test_get_wiki_page_by_id_without_content() -> None:
    client = _make_client()

    with patch.object(client, "send_request") as mock_send:
        mock_send.return_value = Response(
            status_code=200,
            json={"id": 1, "path": "/Home"},
        )

        page = await client._get_wiki_page_by_id(
            "proj-1", "wiki-uuid-1", "MyProject.wiki", 1
        )

        assert page is not None
        mock_send.assert_called_once_with(
            "GET",
            f"{MOCK_ORG_URL}/proj-1/_apis/wiki/wikis/wiki-uuid-1/pages/1",
            params={"api-version": "7.1"},
        )


@pytest.mark.asyncio
async def test_get_wiki_page_by_id_returns_none_on_404() -> None:
    client = _make_client()

    with patch.object(client, "send_request", return_value=None):
        page = await client._get_wiki_page_by_id(
            "proj-1", "wiki-uuid-1", "MyProject.wiki", 999
        )

        assert page is None


# ── generate_wiki_pages ───────────────────────────────────────────────


@pytest.mark.asyncio
async def test_generate_wiki_pages_filters_by_type(
    mock_event_context: None,
) -> None:
    client = _make_client()

    wiki_project = {**MOCK_WIKI_PROJECT, "__project": MOCK_PROJECT}
    wiki_code = {**MOCK_WIKI_CODE, "__project": MOCK_PROJECT}

    async def mock_generate_projects(
        *args: Any, **kwargs: Any
    ) -> AsyncGenerator[List[Dict[str, Any]], None]:
        yield [MOCK_PROJECT]

    with (
        patch.object(
            client,
            "generate_projects",
            side_effect=mock_generate_projects,
        ),
        patch.object(
            client,
            "_get_wikis_for_project",
            return_value=[wiki_project, wiki_code],
        ),
        patch.object(client, "get_wiki_pages_batch") as mock_batch,
    ):

        async def mock_pages(
            *args: Any, **kwargs: Any
        ) -> AsyncGenerator[List[Dict[str, Any]], None]:
            yield [{"id": 1, "path": "/Home"}]

        mock_batch.side_effect = mock_pages

        all_pages: List[Dict[str, Any]] = []
        async for batch in client.generate_wiki_pages(wiki_type="projectWiki"):
            all_pages.extend(batch)

        assert len(all_pages) == 1
        assert all_pages[0]["__wiki"] == wiki_project
        # get_wiki_pages_batch called only once (codeWiki skipped)
        mock_batch.assert_called_once()


@pytest.mark.asyncio
async def test_generate_wiki_pages_no_filter(
    mock_event_context: None,
) -> None:
    client = _make_client()

    wiki_project = {**MOCK_WIKI_PROJECT, "__project": MOCK_PROJECT}
    wiki_code = {**MOCK_WIKI_CODE, "__project": MOCK_PROJECT}

    async def mock_generate_projects(
        *args: Any, **kwargs: Any
    ) -> AsyncGenerator[List[Dict[str, Any]], None]:
        yield [MOCK_PROJECT]

    call_count = 0

    async def mock_pages(
        *args: Any, **kwargs: Any
    ) -> AsyncGenerator[List[Dict[str, Any]], None]:
        nonlocal call_count
        call_count += 1
        yield [{"id": call_count, "path": f"/Page{call_count}"}]

    with (
        patch.object(
            client,
            "generate_projects",
            side_effect=mock_generate_projects,
        ),
        patch.object(
            client,
            "_get_wikis_for_project",
            return_value=[wiki_project, wiki_code],
        ),
        patch.object(
            client,
            "get_wiki_pages_batch",
            side_effect=mock_pages,
        ),
    ):
        all_pages: List[Dict[str, Any]] = []
        async for batch in client.generate_wiki_pages(wiki_type=None):
            all_pages.extend(batch)

        assert len(all_pages) == 2
        assert call_count == 2


@pytest.mark.asyncio
async def test_generate_wiki_pages_with_content_enrichment(
    mock_event_context: None,
) -> None:
    client = _make_client()

    wiki = {**MOCK_WIKI_PROJECT, "__project": MOCK_PROJECT}

    async def mock_generate_projects(
        *args: Any, **kwargs: Any
    ) -> AsyncGenerator[List[Dict[str, Any]], None]:
        yield [MOCK_PROJECT]

    async def mock_pages(
        *args: Any, **kwargs: Any
    ) -> AsyncGenerator[List[Dict[str, Any]], None]:
        yield [{"id": 1, "path": "/Home"}]

    with (
        patch.object(
            client,
            "generate_projects",
            side_effect=mock_generate_projects,
        ),
        patch.object(
            client,
            "_get_wikis_for_project",
            return_value=[wiki],
        ),
        patch.object(
            client,
            "get_wiki_pages_batch",
            side_effect=mock_pages,
        ),
        patch.object(
            client,
            "_get_wiki_page_by_id",
            return_value=MOCK_FULL_PAGE,
        ),
    ):
        all_pages: List[Dict[str, Any]] = []
        async for batch in client.generate_wiki_pages(include_content=True):
            all_pages.extend(batch)

        assert len(all_pages) == 1
        assert all_pages[0]["content"] == "# Home\n\nWelcome."
        assert all_pages[0]["__wiki"] == wiki
        assert all_pages[0]["__project"] == MOCK_PROJECT


@pytest.mark.asyncio
async def test_generate_wiki_pages_without_content_skips_enrichment(
    mock_event_context: None,
) -> None:
    client = _make_client()

    wiki = {**MOCK_WIKI_PROJECT, "__project": MOCK_PROJECT}

    async def mock_generate_projects(
        *args: Any, **kwargs: Any
    ) -> AsyncGenerator[List[Dict[str, Any]], None]:
        yield [MOCK_PROJECT]

    async def mock_pages(
        *args: Any, **kwargs: Any
    ) -> AsyncGenerator[List[Dict[str, Any]], None]:
        yield MOCK_PAGES

    with (
        patch.object(
            client,
            "generate_projects",
            side_effect=mock_generate_projects,
        ),
        patch.object(
            client,
            "_get_wikis_for_project",
            return_value=[wiki],
        ),
        patch.object(
            client,
            "get_wiki_pages_batch",
            side_effect=mock_pages,
        ),
        patch.object(client, "_get_wiki_page_by_id") as mock_get_page,
    ):
        all_pages: List[Dict[str, Any]] = []
        async for batch in client.generate_wiki_pages(include_content=False):
            all_pages.extend(batch)

        assert len(all_pages) == 4
        mock_get_page.assert_not_called()
        for page in all_pages:
            assert page["__wiki"] == wiki
            assert page["__project"] == MOCK_PROJECT


# ── _enrich_pages_with_content ─────────────────────────────────────────


@pytest.mark.asyncio
async def test_enrich_pages_handles_partial_failure() -> None:
    client = _make_client()

    wiki = {**MOCK_WIKI_PROJECT, "__project": MOCK_PROJECT}
    pages = [{"id": 1, "path": "/Good"}, {"id": 2, "path": "/Bad"}]

    async def mock_get_page(
        project_id: str,
        wiki_id: str,
        wiki_name: str,
        page_id: int,
        include_content: bool = False,
        api_version: str = "7.1",
    ) -> Dict[str, Any] | None:
        if page_id == 2:
            raise ConnectionError("network failure")
        return {"id": 1, "path": "/Good", "content": "good"}

    with patch.object(client, "_get_wiki_page_by_id", side_effect=mock_get_page):
        semaphore = asyncio.BoundedSemaphore(10)
        result = await client._enrich_pages_with_content(
            "proj-1", wiki, pages, semaphore
        )

    assert len(result) == 1
    assert result[0]["path"] == "/Good"
    assert result[0]["__wiki"] == wiki
