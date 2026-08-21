from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest
from port_ocean.context.ocean import initialize_port_ocean_context
from port_ocean.exceptions.context import PortOceanContextAlreadyInitializedError

from clients.auth import TokenAuthenticator
from clients.databricks import DatabricksClient

TEST_CONFIG: dict[str, str] = {
    "workspace_url": "https://workspace.cloud.databricks.com",
    "token": "test-token",
    "app_host": "https://app.example.com",
}


@pytest.fixture(autouse=True)
def mock_ocean_context() -> None:
    try:
        mock_ocean_app = MagicMock()
        mock_ocean_app.config.integration.config = {
            "workspace_url": TEST_CONFIG["workspace_url"],
            "token": TEST_CONFIG["token"],
        }
        mock_ocean_app.config.client_timeout = 30.0
        mock_ocean_app.integration_router = MagicMock()
        mock_ocean_app.port_client = MagicMock()
        mock_ocean_app.base_url = TEST_CONFIG["app_host"]
        mock_ocean_app.cache_provider = AsyncMock()
        mock_ocean_app.cache_provider.get.return_value = None
        initialize_port_ocean_context(mock_ocean_app)
    except PortOceanContextAlreadyInitializedError:
        pass


@pytest.fixture
def client() -> DatabricksClient:
    return DatabricksClient(
        workspace_url=TEST_CONFIG["workspace_url"],
        authenticator=TokenAuthenticator(TEST_CONFIG["token"]),
        http_client=httpx.AsyncClient(),
    )


def _mock_response(payload: dict[str, Any]) -> MagicMock:
    response = MagicMock()
    response.json.return_value = payload
    response.content = b"1"
    response.raise_for_status.return_value = None
    return response


class TestGetClusters:
    @pytest.mark.asyncio
    async def test_single_page(self, client: DatabricksClient) -> None:
        response = _mock_response({"clusters": [{"cluster_id": "c1"}]})
        with patch.object(
            client.http_client, "request", AsyncMock(return_value=response)
        ):
            batches = [batch async for batch in client.get_clusters()]
        assert batches == [[{"cluster_id": "c1"}]]

    @pytest.mark.asyncio
    async def test_empty(self, client: DatabricksClient) -> None:
        response = _mock_response({})
        with patch.object(
            client.http_client, "request", AsyncMock(return_value=response)
        ):
            batches = [batch async for batch in client.get_clusters()]
        assert batches == [[]]


class TestGetJobs:
    @pytest.mark.asyncio
    async def test_multi_page_continuation(self, client: DatabricksClient) -> None:
        responses = [
            _mock_response(
                {"jobs": [{"job_id": 1}], "has_more": True, "next_page_token": "tok-2"}
            ),
            _mock_response({"jobs": [{"job_id": 2}], "has_more": False}),
        ]
        with patch.object(
            client.http_client, "request", AsyncMock(side_effect=responses)
        ):
            collected: list[dict[str, Any]] = []
            async for batch in client.get_jobs():
                collected.extend(batch)

        assert collected == [{"job_id": 1}, {"job_id": 2}]

    @pytest.mark.asyncio
    async def test_single_page_no_more(self, client: DatabricksClient) -> None:
        response = _mock_response({"jobs": [{"job_id": 1}], "has_more": False})
        with patch.object(
            client.http_client, "request", AsyncMock(return_value=response)
        ):
            batches = [batch async for batch in client.get_jobs()]
        assert batches == [[{"job_id": 1}]]

    @pytest.mark.asyncio
    async def test_empty(self, client: DatabricksClient) -> None:
        response = _mock_response({"has_more": False})
        with patch.object(
            client.http_client, "request", AsyncMock(return_value=response)
        ):
            batches = [batch async for batch in client.get_jobs()]
        assert batches == [[]]

    @pytest.mark.asyncio
    async def test_expand_tasks_param(self, client: DatabricksClient) -> None:
        response = _mock_response({"jobs": [], "has_more": False})
        mock_request = AsyncMock(return_value=response)
        with patch.object(client.http_client, "request", mock_request):
            async for _ in client.get_jobs(expand_tasks=True):
                pass
        assert mock_request.call_args.kwargs["params"]["expand_tasks"] == "true"


class TestGetJobRuns:
    @pytest.mark.asyncio
    async def test_multi_page_continuation(self, client: DatabricksClient) -> None:
        responses = [
            _mock_response(
                {"runs": [{"run_id": 1}], "has_more": True, "next_page_token": "tok-2"}
            ),
            _mock_response({"runs": [{"run_id": 2}], "has_more": False}),
        ]
        with patch.object(
            client.http_client, "request", AsyncMock(side_effect=responses)
        ):
            collected: list[dict[str, Any]] = []
            async for batch in client.get_job_runs():
                collected.extend(batch)
        assert collected == [{"run_id": 1}, {"run_id": 2}]

    @pytest.mark.asyncio
    async def test_completed_only_param(self, client: DatabricksClient) -> None:
        response = _mock_response({"runs": [], "has_more": False})
        mock_request = AsyncMock(return_value=response)
        with patch.object(client.http_client, "request", mock_request):
            async for _ in client.get_job_runs(completed_only=True):
                pass
        assert mock_request.call_args.kwargs["params"]["completed_only"] == "true"

    @pytest.mark.asyncio
    async def test_get_job_run_single_resource(self, client: DatabricksClient) -> None:
        response = _mock_response({"run_id": 1, "state": {"result_state": "SUCCESS"}})
        with patch.object(
            client.http_client, "request", AsyncMock(return_value=response)
        ):
            result = await client.get_job_run("1")
        assert result == {"run_id": 1, "state": {"result_state": "SUCCESS"}}

    @pytest.mark.asyncio
    async def test_get_job_single_resource(self, client: DatabricksClient) -> None:
        response = _mock_response({"job_id": 1, "settings": {"name": "job-a"}})
        with patch.object(
            client.http_client, "request", AsyncMock(return_value=response)
        ):
            result = await client.get_job("1")
        assert result == {"job_id": 1, "settings": {"name": "job-a"}}


class TestGetPipelines:
    @pytest.mark.asyncio
    async def test_multi_page_continuation(self, client: DatabricksClient) -> None:
        responses = [
            _mock_response(
                {"pipelines": [{"pipeline_id": "p1"}], "next_page_token": "tok-2"}
            ),
            _mock_response({"pipelines": [{"pipeline_id": "p2"}]}),
        ]
        with patch.object(
            client.http_client, "request", AsyncMock(side_effect=responses)
        ):
            collected: list[dict[str, Any]] = []
            async for batch in client.get_pipelines():
                collected.extend(batch)
        assert collected == [{"pipeline_id": "p1"}, {"pipeline_id": "p2"}]

    @pytest.mark.asyncio
    async def test_empty(self, client: DatabricksClient) -> None:
        response = _mock_response({})
        with patch.object(
            client.http_client, "request", AsyncMock(return_value=response)
        ):
            batches = [batch async for batch in client.get_pipelines()]
        assert batches == [[]]


class TestGetSqlWarehouses:
    @pytest.mark.asyncio
    async def test_single_page(self, client: DatabricksClient) -> None:
        response = _mock_response({"warehouses": [{"id": "w1"}]})
        with patch.object(
            client.http_client, "request", AsyncMock(return_value=response)
        ):
            batches = [batch async for batch in client.get_sql_warehouses()]
        assert batches == [[{"id": "w1"}]]


class TestGetCatalogs:
    @pytest.mark.asyncio
    async def test_multi_page_continuation(self, client: DatabricksClient) -> None:
        responses = [
            _mock_response(
                {"catalogs": [{"name": "main"}], "next_page_token": "tok-2"}
            ),
            _mock_response({"catalogs": [{"name": "dev"}]}),
        ]
        with patch.object(
            client.http_client, "request", AsyncMock(side_effect=responses)
        ):
            collected: list[dict[str, Any]] = []
            async for batch in client.get_catalogs():
                collected.extend(batch)
        assert collected == [{"name": "main"}, {"name": "dev"}]

    @pytest.mark.asyncio
    async def test_empty(self, client: DatabricksClient) -> None:
        response = _mock_response({})
        with patch.object(
            client.http_client, "request", AsyncMock(return_value=response)
        ):
            batches = [batch async for batch in client.get_catalogs()]
        assert batches == [[]]


class TestGetSchemasAndTables:
    @pytest.mark.asyncio
    async def test_get_schemas_single_page(self, client: DatabricksClient) -> None:
        response = _mock_response(
            {"schemas": [{"name": "default", "catalog_name": "main"}]}
        )
        with patch.object(
            client.http_client, "request", AsyncMock(return_value=response)
        ):
            batches = [batch async for batch in client.get_schemas("main")]
        assert batches == [[{"name": "default", "catalog_name": "main"}]]

    @pytest.mark.asyncio
    async def test_get_tables_single_page(self, client: DatabricksClient) -> None:
        response = _mock_response(
            {
                "tables": [
                    {
                        "name": "orders",
                        "catalog_name": "main",
                        "schema_name": "default",
                    }
                ]
            }
        )
        with patch.object(
            client.http_client, "request", AsyncMock(return_value=response)
        ):
            batches = [batch async for batch in client.get_tables("main", "default")]
        assert batches == [
            [{"name": "orders", "catalog_name": "main", "schema_name": "default"}]
        ]


class TestCatalogToSchemaFanOut:
    @pytest.mark.asyncio
    async def test_get_all_schemas_fans_out_per_catalog(
        self, client: DatabricksClient
    ) -> None:
        catalogs_response = _mock_response(
            {"catalogs": [{"name": "main"}, {"name": "dev"}]}
        )
        schemas_main_response = _mock_response(
            {"schemas": [{"name": "default", "catalog_name": "main"}]}
        )
        schemas_dev_response = _mock_response(
            {"schemas": [{"name": "sandbox", "catalog_name": "dev"}]}
        )

        with patch.object(
            client.http_client,
            "request",
            AsyncMock(
                side_effect=[
                    catalogs_response,
                    schemas_main_response,
                    schemas_dev_response,
                ]
            ),
        ):
            collected: list[dict[str, Any]] = []
            async for batch in client.get_all_schemas():
                collected.extend(batch)

        assert collected == [
            {"name": "default", "catalog_name": "main"},
            {"name": "sandbox", "catalog_name": "dev"},
        ]

    @pytest.mark.asyncio
    async def test_get_all_catalogs_filters_by_name(
        self, client: DatabricksClient
    ) -> None:
        catalogs_response = _mock_response(
            {"catalogs": [{"name": "main"}, {"name": "dev"}]}
        )
        with patch.object(
            client.http_client, "request", AsyncMock(return_value=catalogs_response)
        ):
            batches = [
                batch async for batch in client.get_all_catalogs(catalog_names=["main"])
            ]
        assert batches == [[{"name": "main"}]]


class TestSchemaToTableFanOut:
    @pytest.mark.asyncio
    async def test_get_all_tables_fans_out_per_schema(
        self, client: DatabricksClient
    ) -> None:
        catalogs_response = _mock_response({"catalogs": [{"name": "main"}]})
        schemas_response = _mock_response(
            {"schemas": [{"name": "default", "catalog_name": "main"}]}
        )
        tables_response = _mock_response(
            {
                "tables": [
                    {"name": "orders", "catalog_name": "main", "schema_name": "default"}
                ]
            }
        )

        with patch.object(
            client.http_client,
            "request",
            AsyncMock(
                side_effect=[catalogs_response, schemas_response, tables_response]
            ),
        ):
            collected: list[dict[str, Any]] = []
            async for batch in client.get_all_tables():
                collected.extend(batch)

        assert collected == [
            {"name": "orders", "catalog_name": "main", "schema_name": "default"}
        ]

    @pytest.mark.asyncio
    async def test_get_all_tables_continues_on_partial_failure(
        self, client: DatabricksClient
    ) -> None:
        catalogs_response = _mock_response(
            {"catalogs": [{"name": "main"}, {"name": "dev"}]}
        )
        schemas_main_response = _mock_response(
            {"schemas": [{"name": "default", "catalog_name": "main"}]}
        )
        schemas_dev_response = _mock_response(
            {"schemas": [{"name": "sandbox", "catalog_name": "dev"}]}
        )
        tables_dev_response = _mock_response(
            {
                "tables": [
                    {"name": "logs", "catalog_name": "dev", "schema_name": "sandbox"}
                ]
            }
        )

        async def request_side_effect(*args: Any, **kwargs: Any) -> MagicMock:
            url = kwargs.get("url", "")
            params = kwargs.get("params") or {}
            if url.endswith("unity-catalog/catalogs"):
                return catalogs_response
            if (
                url.endswith("unity-catalog/schemas")
                and params.get("catalog_name") == "main"
            ):
                return schemas_main_response
            if (
                url.endswith("unity-catalog/schemas")
                and params.get("catalog_name") == "dev"
            ):
                return schemas_dev_response
            if (
                params.get("catalog_name") == "main"
                and params.get("schema_name") == "default"
            ):
                raise httpx.HTTPStatusError(
                    "boom", request=MagicMock(), response=MagicMock(status_code=500)
                )
            if (
                params.get("catalog_name") == "dev"
                and params.get("schema_name") == "sandbox"
            ):
                return tables_dev_response
            raise AssertionError(f"Unexpected request: {url} {params}")

        with patch.object(
            client.http_client, "request", AsyncMock(side_effect=request_side_effect)
        ):
            collected: list[dict[str, Any]] = []
            async for batch in client.get_all_tables():
                collected.extend(batch)

        assert collected == [
            {"name": "logs", "catalog_name": "dev", "schema_name": "sandbox"}
        ]


class TestWebhookDestination:
    @pytest.mark.asyncio
    async def test_creates_destination_when_not_exists(
        self, client: DatabricksClient
    ) -> None:
        list_response = _mock_response({"results": []})
        create_response = _mock_response({"id": "dest-1"})

        with patch.object(
            client.http_client,
            "request",
            AsyncMock(side_effect=[list_response, create_response]),
        ) as mock_request:
            await client.create_webhook_destination_if_not_exists(
                "https://app.example.com/integration/webhook"
            )

        assert mock_request.await_count == 2
        create_call = mock_request.call_args_list[1]
        assert create_call.kwargs["method"] == "POST"

    @pytest.mark.asyncio
    async def test_skips_creation_when_already_exists_with_same_url(
        self, client: DatabricksClient
    ) -> None:
        list_response = _mock_response(
            {
                "results": [
                    {"display_name": "port-ocean-databricks-webhook", "id": "dest-1"}
                ]
            }
        )
        full_destination_response = _mock_response(
            {
                "id": "dest-1",
                "display_name": "port-ocean-databricks-webhook",
                "config": {
                    "generic_webhook": {
                        "url": "https://app.example.com/integration/webhook"
                    }
                },
            }
        )

        with patch.object(
            client.http_client,
            "request",
            AsyncMock(side_effect=[list_response, full_destination_response]),
        ) as mock_request:
            await client.create_webhook_destination_if_not_exists(
                "https://app.example.com/integration/webhook"
            )

        assert mock_request.await_count == 2

    @pytest.mark.asyncio
    async def test_recreates_destination_when_url_changed(
        self, client: DatabricksClient
    ) -> None:
        list_response = _mock_response(
            {
                "results": [
                    {"display_name": "port-ocean-databricks-webhook", "id": "dest-1"}
                ]
            }
        )
        full_destination_response = _mock_response(
            {
                "id": "dest-1",
                "config": {
                    "generic_webhook": {"url": "https://old.example.com/webhook"}
                },
            }
        )
        delete_response = _mock_response({})
        create_response = _mock_response({"id": "dest-2"})

        with patch.object(
            client.http_client,
            "request",
            AsyncMock(
                side_effect=[
                    list_response,
                    full_destination_response,
                    delete_response,
                    create_response,
                ]
            ),
        ) as mock_request:
            await client.create_webhook_destination_if_not_exists(
                "https://new.example.com/integration/webhook"
            )

        assert mock_request.await_count == 4
        delete_call = mock_request.call_args_list[2]
        assert delete_call.kwargs["method"] == "DELETE"
        create_call = mock_request.call_args_list[3]
        assert create_call.kwargs["method"] == "POST"


def test_from_ocean_configuration() -> None:
    client = DatabricksClient.from_ocean_configuration()
    assert client.workspace_url == TEST_CONFIG["workspace_url"]
