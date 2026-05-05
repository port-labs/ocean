import pytest
import httpx
from typing import Any, AsyncGenerator
from unittest.mock import AsyncMock, patch, MagicMock
from port_ocean.context.ocean import initialize_port_ocean_context
from port_ocean.exceptions.context import PortOceanContextAlreadyInitializedError

from clients.github_client import GitHubClient
from tests.mocks import (
    organizations_response,
    mock_single_json_signed_url_content,
    mock_ndjson_signed_url_content,
)

BASE_URL = "https://api.github.com"
TOKEN = "test-token"


@pytest.fixture(autouse=True)
def mock_ocean_context() -> None:
    try:
        mock_ocean_app = MagicMock()
        mock_ocean_app.config.integration.config = {
            "github_token": TOKEN,
            "github_host": BASE_URL,
        }
        mock_ocean_app.integration_router = MagicMock()
        mock_ocean_app.port_client = MagicMock()
        mock_ocean_app.cache_provider = AsyncMock()
        mock_ocean_app.cache_provider.get.return_value = None
        initialize_port_ocean_context(mock_ocean_app)
    except PortOceanContextAlreadyInitializedError:
        pass


@pytest.fixture
def github_client() -> GitHubClient:
    return GitHubClient(base_url=BASE_URL, token=TOKEN)


@pytest.fixture
def enterprise_github_client() -> GitHubClient:
    return GitHubClient(
        base_url="https://api.example-github.com",
        token="test-token",
        enterprise_name="test-enterprise",
    )


def _make_user_usage_records(count: int) -> list[dict[str, Any]]:
    return [{"user_id": f"user_{i}", "completions": i} for i in range(count)]


def _make_day_totals_report(count: int) -> list[dict[str, Any]]:
    return [
        {
            "day_totals": [
                {"day": f"2025-01-{str(i).zfill(2)}", "total": i}
                for i in range(1, count + 1)
            ]
        }
    ]


@pytest.fixture
def mock_organization() -> dict[str, Any]:
    return {"login": "test-org", "id": 1}


@pytest.fixture
def mock_enterprise_context() -> dict[str, str]:
    return {"slug": "test-enterprise"}


@pytest.mark.asyncio
async def test_get_organizations_single_page(github_client: GitHubClient) -> None:
    expected_response = organizations_response
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = expected_response
    mock_response.headers = {}

    with patch.object(
        github_client._client, "request", new=AsyncMock(return_value=mock_response)
    ):
        results = []
        async for orgs in github_client.get_organizations():
            results.extend(orgs)

        assert results == expected_response


@pytest.mark.asyncio
async def test_paginated_response(github_client: GitHubClient) -> None:
    first_response = MagicMock()
    first_response.status_code = 200
    first_response.json.return_value = [{"item": 1}]
    first_response.headers = {"Link": f'<{BASE_URL}/paginated?page=2>; rel="next"'}

    second_response = MagicMock()
    second_response.status_code = 200
    second_response.json.return_value = [{"item": 2}]
    second_response.headers = {}

    async_mock = AsyncMock(side_effect=[first_response, second_response])

    with patch.object(github_client, "_send_api_request", new=async_mock):
        results = []
        async for page in github_client._get_paginated_data("paginated"):
            results.extend(page)

        assert results == [{"item": 1}, {"item": 2}]


@pytest.mark.asyncio
async def test_send_api_request_404_returns_empty(github_client: GitHubClient) -> None:
    error_response = httpx.Response(
        status_code=404, request=httpx.Request("get", "https://fake")
    )
    async_mock = AsyncMock(
        side_effect=httpx.HTTPStatusError(
            "Not Found", request=error_response.request, response=error_response
        )
    )

    with patch.object(github_client._client, "request", new=async_mock):
        result = await github_client.send_api_request("get", "not-found")
        assert result == []


def test_resolve_route_params() -> None:
    endpoint = "/orgs/{org}/copilot/metrics/users"
    params = {"org": "acme"}
    result = GitHubClient._resolve_route_params(endpoint, params)
    assert result == "/orgs/acme/copilot/metrics/users"


@pytest.mark.asyncio
async def test_get_new_usage_metrics_returns_empty_when_manifest_has_empty_links(
    github_client: GitHubClient,
) -> None:
    empty_manifest_response = MagicMock()
    empty_manifest_response.status_code = 200
    empty_manifest_response.json.return_value = {"download_links": []}

    with patch.object(
        github_client._client,
        "request",
        new=AsyncMock(return_value=empty_manifest_response),
    ):
        result = [
            batch
            async for batch in github_client.get_organization_usage_metrics(
                organizations_response[0]
            )
        ]

    assert result == []


@pytest.mark.asyncio
async def test_fetch_report_from_signed_url_returns_empty_on_forbidden_error(
    github_client: GitHubClient,
) -> None:
    signed_url = "https://signed.example.com/copilot-report-expired.json"
    expired_url_response = httpx.Response(
        status_code=403, request=httpx.Request("GET", signed_url)
    )
    request_mock = AsyncMock(
        side_effect=httpx.HTTPStatusError(
            "Forbidden",
            request=expired_url_response.request,
            response=expired_url_response,
        )
    )

    with patch.object(github_client._client, "request", new=request_mock):
        result = await github_client._fetch_report_from_signed_url(signed_url)
        assert result == []


@pytest.mark.asyncio
async def test_get_new_usage_metrics_returns_empty_when_api_request_fails(
    github_client: GitHubClient,
) -> None:
    with patch.object(
        github_client, "_send_api_request", new=AsyncMock(return_value=None)
    ):
        result = [
            batch
            async for batch in github_client.get_organization_usage_metrics(
                organizations_response[0]
            )
        ]
        assert result == []


@pytest.mark.asyncio
async def test_get_new_usage_metrics_skips_unexpected_schema(
    github_client: GitHubClient,
) -> None:
    manifest_response = MagicMock()
    manifest_response.status_code = 200
    manifest_response.json.return_value = {
        "download_links": ["https://signed.example.com/unexpected.json"],
        "report_start_day": "2026-02-10",
        "report_end_day": "2026-03-09",
    }

    unexpected_schema_response = httpx.Response(
        status_code=200,
        content=b'{"unexpected_key": "some_value"}',
        request=httpx.Request("GET", "https://signed.example.com/unexpected.json"),
    )

    request_mock = AsyncMock(
        side_effect=[manifest_response, unexpected_schema_response]
    )

    with patch.object(github_client._client, "request", new=request_mock):
        result = [
            batch
            async for batch in github_client.get_organization_usage_metrics(
                organizations_response[0]
            )
        ]
    assert result == [[{"unexpected_key": "some_value"}]]


@pytest.mark.asyncio
async def test_fetch_report_from_signed_url_parses_single_line_json(
    github_client: GitHubClient,
) -> None:
    """_fetch_report_from_signed_url handles a single-line JSON report."""
    import json

    signed_url = "https://signed.example.com/copilot-report-single.json"
    single_json_response = httpx.Response(
        status_code=200,
        content=mock_single_json_signed_url_content,
        request=httpx.Request("GET", signed_url),
    )
    expected = [json.loads(mock_single_json_signed_url_content)]

    with patch.object(
        github_client._client,
        "request",
        new=AsyncMock(return_value=single_json_response),
    ):
        result = await github_client._fetch_report_from_signed_url(signed_url)
        assert result == expected


@pytest.mark.asyncio
async def test_fetch_report_from_signed_url_parses_ndjson(
    github_client: GitHubClient,
) -> None:
    """_fetch_report_from_signed_url parses NDJSON with one JSON object per line."""
    signed_url = "https://signed.example.com/copilot-report-ndjson.json"
    ndjson_response = httpx.Response(
        status_code=200,
        content=mock_ndjson_signed_url_content,
        request=httpx.Request("GET", signed_url),
    )

    expected = [
        {
            "report_start_day": "2026-02-01",
            "report_end_day": "2026-02-28",
            "day_totals": [
                {
                    "org": "acme-corp-test-org",
                    "daily_active_users": 5,
                    "day": "2026-02-01",
                    "code_generation_activity_count": 100,
                }
            ],
        },
        {
            "report_start_day": "2026-02-01",
            "report_end_day": "2026-02-28",
            "day_totals": [
                {
                    "org": "acme-corp-test-org",
                    "daily_active_users": 42,
                    "day": "2026-03-05",
                    "code_generation_activity_count": 150,
                }
            ],
        },
    ]

    with patch.object(
        github_client._client, "request", new=AsyncMock(return_value=ndjson_response)
    ):
        result = await github_client._fetch_report_from_signed_url(signed_url)
        assert result == expected


@pytest.mark.asyncio
async def test_get_users_usage_metrics_returns_batches_from_signed_urls(
    github_client: GitHubClient,
) -> None:
    organization = {"login": "acme-corp-test-org"}
    manifest_response = MagicMock()
    manifest_response.status_code = 200
    manifest_response.json.return_value = {
        "download_links": [
            "https://signed.example.com/users-report-1.ndjson",
            "https://signed.example.com/users-report-2.ndjson",
        ],
        "report_start_day": "2026-03-01",
        "report_end_day": "2026-03-28",
    }

    fetch_report_mock = AsyncMock(
        side_effect=[
            [
                {
                    "day": "2026-03-12",
                    "organization_id": "1234567890",
                    "user_login": "bob",
                    "code_generation_activity_count": 19,
                    "code_acceptance_activity_count": 8,
                }
            ],
            [
                {
                    "day": "2026-03-12",
                    "organization_id": "1234567890",
                    "user_login": "alice",
                    "code_generation_activity_count": 11,
                    "code_acceptance_activity_count": 5,
                }
            ],
        ]
    )

    with (
        patch.object(
            github_client,
            "_send_api_request",
            new=AsyncMock(return_value=manifest_response),
        ),
        patch.object(
            github_client, "_fetch_report_from_signed_url", new=fetch_report_mock
        ),
    ):
        result = [
            batch
            async for batch in github_client._get_users_usage_metrics(organization)
        ]

    assert result == [
        [
            {
                "day": "2026-03-12",
                "organization_id": "1234567890",
                "user_login": "bob",
                "code_generation_activity_count": 19,
                "code_acceptance_activity_count": 8,
            }
        ],
        [
            {
                "day": "2026-03-12",
                "organization_id": "1234567890",
                "user_login": "alice",
                "code_generation_activity_count": 11,
                "code_acceptance_activity_count": 5,
            }
        ],
    ]


@pytest.mark.asyncio
async def test_fetch_users_usage_metrics_enriches_records_across_org_batches(
    github_client: GitHubClient,
) -> None:
    org_a = {"login": "acme-a", "id": 1}
    org_b = {"login": "acme-b", "id": 2}
    org_c = {"login": "acme-c", "id": 3}

    async def organizations_generator() -> AsyncGenerator[list[dict[str, Any]], None]:
        yield [org_a, org_b]
        yield [org_c]

    async def users_usage_generator(
        organization: dict[str, Any],
    ) -> AsyncGenerator[list[dict[str, Any]], None]:
        if organization["login"] == "acme-a":
            yield [{"user_login": "alice", "day": "2026-03-12"}]
            return
        if organization["login"] == "acme-b":
            yield [{"user_login": "bob", "day": "2026-03-12"}]
            return
        yield [{"user_login": "charlie", "day": "2026-03-12"}]

    with (
        patch.object(github_client, "get_organizations", new=organizations_generator),
        patch.object(
            github_client, "_get_users_usage_metrics", new=users_usage_generator
        ),
    ):
        result = [batch async for batch in github_client.fetch_users_usage_metrics()]

    assert result == [
        [{"user_login": "alice", "day": "2026-03-12", "__organization": org_a}],
        [{"user_login": "bob", "day": "2026-03-12", "__organization": org_b}],
        [{"user_login": "charlie", "day": "2026-03-12", "__organization": org_c}],
    ]


@pytest.mark.asyncio
async def test_get_enterprise_usage_metrics_returns_batches_from_signed_urls() -> None:
    enterprise_name = "acme-enterprise"
    enterprise_client = GitHubClient(
        base_url=BASE_URL,
        token=TOKEN,
        enterprise_name=enterprise_name,
    )
    manifest_response = MagicMock()
    manifest_response.status_code = 200
    manifest_response.json.return_value = {
        "download_links": [
            "https://signed.example.com/enterprise-report-1.ndjson",
            "https://signed.example.com/enterprise-report-2.ndjson",
        ],
        "report_start_day": "2026-03-01",
        "report_end_day": "2026-03-28",
    }
    fetch_report_mock = AsyncMock(
        side_effect=[
            [{"day_totals": [{"day": "2026-03-12", "daily_active_users": 11}]}],
            [{"day_totals": [{"day": "2026-03-13", "daily_active_users": 9}]}],
        ]
    )

    with (
        patch.object(
            enterprise_client,
            "_send_api_request",
            new=AsyncMock(return_value=manifest_response),
        ),
        patch.object(
            enterprise_client, "_fetch_report_from_signed_url", new=fetch_report_mock
        ),
    ):
        result = [
            batch async for batch in enterprise_client._get_enterprise_usage_metrics()
        ]

    assert result == [
        [{"day_totals": [{"day": "2026-03-12", "daily_active_users": 11}]}],
        [{"day_totals": [{"day": "2026-03-13", "daily_active_users": 9}]}],
    ]


@pytest.mark.asyncio
async def test_fetch_enterprise_usage_metrics_enriches_day_totals() -> None:
    enterprise_name = "acme-enterprise"
    enterprise_client = GitHubClient(
        base_url=BASE_URL,
        token=TOKEN,
        enterprise_name=enterprise_name,
    )

    async def enterprise_usage_generator() -> (
        AsyncGenerator[list[dict[str, Any]], None]
    ):
        yield [{"day_totals": [{"day": "2026-03-12", "daily_active_users": 7}]}]
        yield [{"day_totals": [{"day": "2026-03-13", "daily_active_users": 5}]}]

    with patch.object(
        enterprise_client,
        "_get_enterprise_usage_metrics",
        new=enterprise_usage_generator,
    ):
        result = [
            batch async for batch in enterprise_client.fetch_enterprise_usage_metrics()
        ]

    assert result == [
        [
            {
                "day": "2026-03-12",
                "daily_active_users": 7,
                "__enterprise": {"slug": enterprise_name},
            }
        ],
        [
            {
                "day": "2026-03-13",
                "daily_active_users": 5,
                "__enterprise": {"slug": enterprise_name},
            }
        ],
    ]


@pytest.mark.asyncio
async def test_get_enterprise_users_usage_metrics_returns_batches_from_signed_urls() -> (
    None
):
    enterprise_name = "acme-enterprise"
    enterprise_client = GitHubClient(
        base_url=BASE_URL,
        token=TOKEN,
        enterprise_name=enterprise_name,
    )
    manifest_response = MagicMock()
    manifest_response.status_code = 200
    manifest_response.json.return_value = {
        "download_links": [
            "https://signed.example.com/enterprise-users-report-1.ndjson",
            "https://signed.example.com/enterprise-users-report-2.ndjson",
        ],
        "report_start_day": "2026-03-01",
        "report_end_day": "2026-03-28",
    }
    fetch_report_mock = AsyncMock(
        side_effect=[
            [{"day": "2026-03-12", "user_login": "alice"}],
            [{"day": "2026-03-12", "user_login": "bob"}],
        ]
    )

    with (
        patch.object(
            enterprise_client,
            "_send_api_request",
            new=AsyncMock(return_value=manifest_response),
        ),
        patch.object(
            enterprise_client, "_fetch_report_from_signed_url", new=fetch_report_mock
        ),
    ):
        result = [
            batch
            async for batch in enterprise_client._get_enterprise_users_usage_metrics()
        ]

    assert result == [
        [{"day": "2026-03-12", "user_login": "alice"}],
        [{"day": "2026-03-12", "user_login": "bob"}],
    ]


@pytest.mark.asyncio
async def test_fetch_enterprise_users_usage_metrics_enriches_records() -> None:
    enterprise_name = "acme-enterprise"
    enterprise_client = GitHubClient(
        base_url=BASE_URL,
        token=TOKEN,
        enterprise_name=enterprise_name,
    )

    async def enterprise_users_usage_generator() -> (
        AsyncGenerator[list[dict[str, Any]], None]
    ):
        yield [{"day": "2026-03-12", "user_login": "alice"}]
        yield [{"day": "2026-03-12", "user_login": "bob"}]

    with patch.object(
        enterprise_client,
        "_get_enterprise_users_usage_metrics",
        new=enterprise_users_usage_generator,
    ):
        result = [
            batch
            async for batch in enterprise_client.fetch_enterprise_users_usage_metrics()
        ]

    assert result == [
        [
            {
                "day": "2026-03-12",
                "user_login": "alice",
                "__enterprise": {"slug": enterprise_name},
            }
        ],
        [
            {
                "day": "2026-03-12",
                "user_login": "bob",
                "__enterprise": {"slug": enterprise_name},
            }
        ],
    ]


@pytest.mark.asyncio
async def test_large_report_is_split_into_fixed_size_batches(
    github_client: GitHubClient,
    mock_organization: dict[str, Any],
) -> None:
    records = _make_user_usage_records(350)

    async def mock_get_organizations():
        yield [mock_organization]

    async def mock_get_users_usage_metrics(org):
        yield records

    with (
        patch.object(github_client, "get_organizations", mock_get_organizations),
        patch.object(
            github_client,
            "_get_users_usage_metrics",
            mock_get_users_usage_metrics,
        ),
    ):
        batches: list[list[dict[str, Any]]] = []
        async for batch in github_client.fetch_users_usage_metrics():
            batches.append(batch)

    assert len(batches) == 4  # 350 records / 100 per batch = 4 batches
    assert len(batches[0]) == 100
    assert len(batches[1]) == 100
    assert len(batches[2]) == 100
    assert len(batches[3]) == 50


@pytest.mark.asyncio
async def test_all_records_are_present_across_batches_without_data_loss(
    github_client: GitHubClient,
    mock_organization: dict[str, Any],
) -> None:
    records = _make_user_usage_records(250)

    async def mock_get_organizations():
        yield [mock_organization]

    async def mock_get_users_usage_metrics(org):
        yield records

    with (
        patch.object(github_client, "get_organizations", mock_get_organizations),
        patch.object(
            github_client,
            "_get_users_usage_metrics",
            mock_get_users_usage_metrics,
        ),
    ):
        all_records: list[dict[str, Any]] = []
        async for batch in github_client.fetch_users_usage_metrics():
            all_records.extend(batch)

    assert len(all_records) == 250
    assert all(r["user_id"] == f"user_{i}" for i, r in enumerate(all_records))


@pytest.mark.asyncio
async def test_every_record_in_every_batch_is_enriched_with_organization(
    github_client: GitHubClient,
    mock_organization: dict[str, Any],
) -> None:
    records = _make_user_usage_records(150)

    async def mock_get_organizations():
        yield [mock_organization]

    async def mock_get_users_usage_metrics(org):
        yield records

    with (
        patch.object(github_client, "get_organizations", mock_get_organizations),
        patch.object(
            github_client,
            "_get_users_usage_metrics",
            mock_get_users_usage_metrics,
        ),
    ):
        async for batch in github_client.fetch_users_usage_metrics():
            for record in batch:
                assert record["__organization"] == mock_organization


@pytest.mark.asyncio
async def test_small_report_below_chunk_size_yields_single_batch(
    github_client: GitHubClient,
    mock_organization: dict[str, Any],
) -> None:
    records = _make_user_usage_records(50)

    async def mock_get_organizations():
        yield [mock_organization]

    async def mock_get_users_usage_metrics(org):
        yield records

    with (
        patch.object(github_client, "get_organizations", mock_get_organizations),
        patch.object(
            github_client,
            "_get_users_usage_metrics",
            mock_get_users_usage_metrics,
        ),
    ):
        batches: list[list[dict[str, Any]]] = []
        async for batch in github_client.fetch_users_usage_metrics():
            batches.append(batch)

    assert len(batches) == 1
    assert len(batches[0]) == 50


@pytest.mark.asyncio
async def test_empty_report_yields_nothing(
    github_client: GitHubClient,
    mock_organization: dict[str, Any],
) -> None:
    async def mock_get_organizations():
        yield [mock_organization]

    async def mock_get_users_usage_metrics(org):
        yield []

    with (
        patch.object(github_client, "get_organizations", mock_get_organizations),
        patch.object(
            github_client,
            "_get_users_usage_metrics",
            mock_get_users_usage_metrics,
        ),
    ):
        batches: list[list[dict[str, Any]]] = []
        async for batch in github_client.fetch_users_usage_metrics():
            batches.append(batch)

    assert len(batches) == 0


@pytest.mark.asyncio
async def test_multiple_organizations_each_yield_separate_chunked_batches(
    github_client: GitHubClient,
) -> None:
    org_a = {"login": "org-a", "id": 1}
    org_b = {"login": "org-b", "id": 2}
    records_a = _make_user_usage_records(150)
    records_b = _make_user_usage_records(75)

    async def mock_get_organizations():
        yield [org_a, org_b]

    async def mock_get_users_usage_metrics(org):
        if org["login"] == "org-a":
            yield records_a
        else:
            yield records_b

    with (
        patch.object(github_client, "get_organizations", mock_get_organizations),
        patch.object(
            github_client,
            "_get_users_usage_metrics",
            mock_get_users_usage_metrics,
        ),
    ):
        all_records: list[dict[str, Any]] = []
        async for batch in github_client.fetch_users_usage_metrics():
            all_records.extend(batch)

    assert len(all_records) == 225
    org_a_records = [r for r in all_records if r["__organization"]["login"] == "org-a"]
    org_b_records = [r for r in all_records if r["__organization"]["login"] == "org-b"]
    assert len(org_a_records) == 150
    assert len(org_b_records) == 75


@pytest.mark.asyncio
async def test_large_enterprise_report_is_split_into_fixed_size_batches(
    enterprise_github_client: GitHubClient,
) -> None:
    records = _make_user_usage_records(350)

    async def mock_get_enterprise_users_usage_metrics():
        yield records

    with patch.object(
        enterprise_github_client,
        "_get_enterprise_users_usage_metrics",
        mock_get_enterprise_users_usage_metrics,
    ):
        batches: list[list[dict[str, Any]]] = []
        async for (
            batch
        ) in enterprise_github_client.fetch_enterprise_users_usage_metrics():
            batches.append(batch)

    assert len(batches) == 4
    assert len(batches[0]) == 100
    assert len(batches[1]) == 100
    assert len(batches[2]) == 100
    assert len(batches[3]) == 50


@pytest.mark.asyncio
async def test_every_record_in_every_batch_is_enriched_with_enterprise_context(
    enterprise_github_client: GitHubClient,
) -> None:
    records = _make_user_usage_records(150)

    async def mock_get_enterprise_users_usage_metrics():
        yield records

    with patch.object(
        enterprise_github_client,
        "_get_enterprise_users_usage_metrics",
        mock_get_enterprise_users_usage_metrics,
    ):
        async for (
            batch
        ) in enterprise_github_client.fetch_enterprise_users_usage_metrics():
            for record in batch:
                assert record["__enterprise"] == {"slug": "test-enterprise"}


@pytest.mark.asyncio
async def test_all_enterprise_records_present_across_batches_without_data_loss(
    enterprise_github_client: GitHubClient,
) -> None:
    records = _make_user_usage_records(250)

    async def mock_get_enterprise_users_usage_metrics():
        yield records

    with patch.object(
        enterprise_github_client,
        "_get_enterprise_users_usage_metrics",
        mock_get_enterprise_users_usage_metrics,
    ):
        all_records: list[dict[str, Any]] = []
        async for (
            batch
        ) in enterprise_github_client.fetch_enterprise_users_usage_metrics():
            all_records.extend(batch)

    assert len(all_records) == 250


@pytest.mark.asyncio
async def test_empty_enterprise_report_yields_nothing(
    enterprise_github_client: GitHubClient,
) -> None:
    async def mock_get_enterprise_users_usage_metrics():
        yield []

    with patch.object(
        enterprise_github_client,
        "_get_enterprise_users_usage_metrics",
        mock_get_enterprise_users_usage_metrics,
    ):
        batches: list[list[dict[str, Any]]] = []
        async for (
            batch
        ) in enterprise_github_client.fetch_enterprise_users_usage_metrics():
            batches.append(batch)

    assert len(batches) == 0


@pytest.mark.asyncio
async def test_large_day_totals_report_is_split_into_fixed_size_batches(
    github_client: GitHubClient,
    mock_organization: dict[str, Any],
) -> None:
    reports = _make_day_totals_report(350)

    async def mock_get_organizations():
        yield [mock_organization]

    async def mock_get_organization_usage_metrics(org):
        yield reports

    with (
        patch.object(github_client, "get_organizations", mock_get_organizations),
        patch.object(
            github_client,
            "get_organization_usage_metrics",
            mock_get_organization_usage_metrics,
        ),
    ):
        batches: list[list[dict[str, Any]]] = []
        async for batch in github_client.fetch_organization_usage_metrics():
            batches.append(batch)

    assert len(batches) == 4
    assert len(batches[0]) == 100
    assert len(batches[1]) == 100
    assert len(batches[2]) == 100
    assert len(batches[3]) == 50


@pytest.mark.asyncio
async def test_all_day_totals_records_present_across_batches_without_data_loss(
    github_client: GitHubClient,
    mock_organization: dict[str, Any],
) -> None:
    reports = _make_day_totals_report(200)

    async def mock_get_organizations():
        yield [mock_organization]

    async def mock_get_organization_usage_metrics(org):
        yield reports

    with (
        patch.object(github_client, "get_organizations", mock_get_organizations),
        patch.object(
            github_client,
            "get_organization_usage_metrics",
            mock_get_organization_usage_metrics,
        ),
    ):
        all_records: list[dict[str, Any]] = []
        async for batch in github_client.fetch_organization_usage_metrics():
            all_records.extend(batch)

    assert len(all_records) == 200


@pytest.mark.asyncio
async def test_report_with_no_day_totals_yields_nothing(
    github_client: GitHubClient,
    mock_organization: dict[str, Any],
) -> None:
    reports = [{"other_field": "value"}]  # no day_totals key

    async def mock_get_organizations():
        yield [mock_organization]

    async def mock_get_organization_usage_metrics(org):
        yield reports

    with (
        patch.object(github_client, "get_organizations", mock_get_organizations),
        patch.object(
            github_client,
            "get_organization_usage_metrics",
            mock_get_organization_usage_metrics,
        ),
    ):
        batches: list[list[dict[str, Any]]] = []
        async for batch in github_client.fetch_organization_usage_metrics():
            batches.append(batch)

    assert len(batches) == 0


@pytest.mark.asyncio
async def test_large_enterprise_day_totals_split_into_fixed_size_batches(
    enterprise_github_client: GitHubClient,
) -> None:
    reports = _make_day_totals_report(350)

    async def mock_get_enterprise_usage_metrics():
        yield reports

    with patch.object(
        enterprise_github_client,
        "_get_enterprise_usage_metrics",
        mock_get_enterprise_usage_metrics,
    ):
        batches: list[list[dict[str, Any]]] = []
        async for batch in enterprise_github_client.fetch_enterprise_usage_metrics():
            batches.append(batch)

    assert len(batches) == 4
    assert len(batches[0]) == 100
    assert len(batches[1]) == 100
    assert len(batches[2]) == 100
    assert len(batches[3]) == 50


@pytest.mark.asyncio
async def test_every_enterprise_day_total_enriched_with_enterprise_context(
    enterprise_github_client: GitHubClient,
) -> None:
    reports = _make_day_totals_report(150)

    async def mock_get_enterprise_usage_metrics():
        yield reports

    with patch.object(
        enterprise_github_client,
        "_get_enterprise_usage_metrics",
        mock_get_enterprise_usage_metrics,
    ):
        async for batch in enterprise_github_client.fetch_enterprise_usage_metrics():
            for record in batch:
                assert record["__enterprise"] == {"slug": "test-enterprise"}


@pytest.mark.asyncio
async def test_enterprise_report_with_no_day_totals_yields_nothing(
    enterprise_github_client: GitHubClient,
) -> None:
    reports = [{"other_field": "value"}]

    async def mock_get_enterprise_usage_metrics():
        yield reports

    with patch.object(
        enterprise_github_client,
        "_get_enterprise_usage_metrics",
        mock_get_enterprise_usage_metrics,
    ):
        batches: list[list[dict[str, Any]]] = []
        async for batch in enterprise_github_client.fetch_enterprise_usage_metrics():
            batches.append(batch)

    assert len(batches) == 0


@pytest.mark.asyncio
async def test_all_enterprise_day_totals_present_across_batches_without_data_loss(
    enterprise_github_client: GitHubClient,
) -> None:
    reports = _make_day_totals_report(250)

    async def mock_get_enterprise_usage_metrics():
        yield reports

    with patch.object(
        enterprise_github_client,
        "_get_enterprise_usage_metrics",
        mock_get_enterprise_usage_metrics,
    ):
        all_records: list[dict[str, Any]] = []
        async for batch in enterprise_github_client.fetch_enterprise_usage_metrics():
            all_records.extend(batch)

    assert len(all_records) == 250
