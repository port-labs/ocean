import asyncio
from http import HTTPStatus
from typing import Any, AsyncGenerator, Optional

import httpx
from loguru import logger
from port_ocean.context.ocean import ocean
from port_ocean.helpers.async_client import OceanAsyncClient
from port_ocean.helpers.retry import RetryConfig

from clients.auth import DatabricksAuthenticator, build_authenticator
from consts import WEBHOOK_DESTINATION_NAME

MAX_CONCURRENT_TABLE_REQUESTS = 10
PIPELINES_PAGE_SIZE = 100

CLUSTERS_ENDPOINT = "api/2.1/clusters/list"
JOBS_ENDPOINT = "api/2.2/jobs/list"
JOB_ENDPOINT = "api/2.2/jobs/get"
JOB_RUNS_ENDPOINT = "api/2.2/jobs/runs/list"
JOB_RUN_ENDPOINT = "api/2.2/jobs/runs/get"
PIPELINES_ENDPOINT = "api/2.0/pipelines"
SQL_WAREHOUSES_ENDPOINT = "api/2.0/sql/warehouses"
CATALOGS_ENDPOINT = "api/2.1/unity-catalog/catalogs"
SCHEMAS_ENDPOINT = "api/2.1/unity-catalog/schemas"
TABLES_ENDPOINT = "api/2.1/unity-catalog/tables"
NOTIFICATION_DESTINATIONS_ENDPOINT = "api/2.0/notification-destinations"


def _build_http_client() -> OceanAsyncClient:
    return OceanAsyncClient(
        retry_config=RetryConfig(
            additional_retry_status_codes=[HTTPStatus.INTERNAL_SERVER_ERROR],
        ),
        timeout=ocean.config.client_timeout,
    )


class DatabricksClient:
    def __init__(
        self,
        workspace_url: str,
        authenticator: DatabricksAuthenticator,
        http_client: Optional[httpx.AsyncClient] = None,
    ) -> None:
        self.workspace_url = workspace_url.rstrip("/")
        self.authenticator = authenticator
        self.http_client = http_client or _build_http_client()

    @classmethod
    def from_ocean_configuration(cls) -> "DatabricksClient":
        config = ocean.integration_config
        workspace_url = config["workspace_url"]
        http_client = _build_http_client()
        authenticator = build_authenticator(
            workspace_url=workspace_url,
            token=config.get("token"),
            client_id=config.get("client_id"),
            client_secret=config.get("client_secret"),
            http_client=http_client,
        )
        return cls(workspace_url, authenticator, http_client)

    async def _send_api_request(
        self,
        endpoint: str,
        method: str = "GET",
        params: Optional[dict[str, Any]] = None,
        json_data: Optional[dict[str, Any]] = None,
    ) -> dict[str, Any]:
        headers = await self.authenticator.get_auth_header()
        url = f"{self.workspace_url}/{endpoint}"
        logger.debug(
            f"Sending Databricks API request: {method} {url} with params: {params}"
        )
        try:
            response = await self.http_client.request(
                method=method,
                url=url,
                params=params,
                json=json_data,
                headers=headers,
            )
            response.raise_for_status()
            return response.json() if response.content else {}
        except httpx.HTTPStatusError as e:
            logger.error(
                f"HTTP error for Databricks endpoint '{endpoint}': "
                f"status {e.response.status_code}, response: {e.response.text}"
            )
            raise
        except httpx.HTTPError as e:
            logger.error(
                f"HTTP error while calling Databricks endpoint '{endpoint}': {e}"
            )
            raise

    async def _get(
        self, endpoint: str, params: Optional[dict[str, Any]] = None
    ) -> dict[str, Any]:
        return await self._send_api_request(endpoint, method="GET", params=params)

    async def _paginate(
        self,
        endpoint: str,
        response_key: str,
        params: Optional[dict[str, Any]] = None,
        has_more_field: Optional[str] = None,
    ) -> AsyncGenerator[list[dict[str, Any]], None]:
        """Paginates a Databricks list endpoint using the `page_token`/`next_page_token`
        idiom, optionally gated by a `has_more`-style boolean field for endpoints that
        expose one (e.g. the Jobs API).
        """
        query_params: dict[str, Any] = dict(params or {})

        while True:
            data = await self._get(endpoint, params=query_params)
            batch = data.get(response_key) or []
            yield batch

            next_token = data.get("next_page_token")
            has_more = (
                bool(data.get(has_more_field)) if has_more_field else bool(next_token)
            )

            if not has_more or not next_token:
                break

            query_params["page_token"] = next_token

    async def get_clusters(self) -> AsyncGenerator[list[dict[str, Any]], None]:
        data = await self._get(CLUSTERS_ENDPOINT)
        yield data.get("clusters") or []

    async def get_jobs(
        self, expand_tasks: bool = False
    ) -> AsyncGenerator[list[dict[str, Any]], None]:
        params: dict[str, Any] = {}
        if expand_tasks:
            params["expand_tasks"] = "true"
        async for batch in self._paginate(
            JOBS_ENDPOINT, "jobs", params=params, has_more_field="has_more"
        ):
            yield batch

    async def get_job(self, job_id: str) -> dict[str, Any]:
        return await self._get(JOB_ENDPOINT, params={"job_id": job_id})

    async def get_job_runs(
        self, completed_only: bool = False
    ) -> AsyncGenerator[list[dict[str, Any]], None]:
        params: dict[str, Any] = {}
        if completed_only:
            params["completed_only"] = "true"
        async for batch in self._paginate(
            JOB_RUNS_ENDPOINT, "runs", params=params, has_more_field="has_more"
        ):
            yield batch

    async def get_job_run(self, run_id: str) -> dict[str, Any]:
        return await self._get(JOB_RUN_ENDPOINT, params={"run_id": run_id})

    async def get_pipelines(self) -> AsyncGenerator[list[dict[str, Any]], None]:
        async for batch in self._paginate(
            PIPELINES_ENDPOINT,
            "pipelines",
            params={"max_results": PIPELINES_PAGE_SIZE},
        ):
            yield batch

    async def get_sql_warehouses(self) -> AsyncGenerator[list[dict[str, Any]], None]:
        data = await self._get(SQL_WAREHOUSES_ENDPOINT)
        yield data.get("warehouses") or []

    async def get_catalogs(self) -> AsyncGenerator[list[dict[str, Any]], None]:
        async for batch in self._paginate(CATALOGS_ENDPOINT, "catalogs"):
            yield batch

    async def get_schemas(
        self, catalog_name: str
    ) -> AsyncGenerator[list[dict[str, Any]], None]:
        async for batch in self._paginate(
            SCHEMAS_ENDPOINT, "schemas", params={"catalog_name": catalog_name}
        ):
            yield batch

    async def get_tables(
        self, catalog_name: str, schema_name: str
    ) -> AsyncGenerator[list[dict[str, Any]], None]:
        async for batch in self._paginate(
            TABLES_ENDPOINT,
            "tables",
            params={"catalog_name": catalog_name, "schema_name": schema_name},
        ):
            yield batch

    async def get_all_catalogs(
        self, catalog_names: Optional[list[str]] = None
    ) -> AsyncGenerator[list[dict[str, Any]], None]:
        """Lists catalogs, optionally scoped to a specific set of catalog names."""
        async for batch in self.get_catalogs():
            if catalog_names:
                batch = [
                    catalog for catalog in batch if catalog.get("name") in catalog_names
                ]
            if batch:
                yield batch

    async def get_all_schemas(
        self, catalog_names: Optional[list[str]] = None
    ) -> AsyncGenerator[list[dict[str, Any]], None]:
        """Lists all catalogs, then fans out to fetch schemas per catalog."""
        async for catalog_batch in self.get_all_catalogs(catalog_names):
            for catalog in catalog_batch:
                async for schema_batch in self.get_schemas(catalog["name"]):
                    if schema_batch:
                        yield schema_batch

    async def get_all_tables(
        self, catalog_names: Optional[list[str]] = None
    ) -> AsyncGenerator[list[dict[str, Any]], None]:
        """Lists all catalogs and schemas, then fans out to fetch tables per
        catalog+schema pair with bounded concurrency, yielding each schema's
        tables as soon as they're ready rather than waiting for every pair to finish.
        """
        schema_refs: list[tuple[str, str]] = []
        async for schema_batch in self.get_all_schemas(catalog_names):
            for schema in schema_batch:
                schema_refs.append((schema["catalog_name"], schema["name"]))

        if not schema_refs:
            return

        semaphore = asyncio.Semaphore(MAX_CONCURRENT_TABLE_REQUESTS)

        async def fetch_tables(
            catalog_name: str, schema_name: str
        ) -> list[dict[str, Any]]:
            async with semaphore:
                tables: list[dict[str, Any]] = []
                async for table_batch in self.get_tables(catalog_name, schema_name):
                    tables.extend(table_batch)
                return tables

        pending = {
            asyncio.create_task(fetch_tables(catalog_name, schema_name)): (
                catalog_name,
                schema_name,
            )
            for catalog_name, schema_name in schema_refs
        }

        while pending:
            done, _ = await asyncio.wait(pending, return_when=asyncio.FIRST_COMPLETED)
            for task in done:
                catalog_name, schema_name = pending.pop(task)
                try:
                    tables = task.result()
                except Exception as e:
                    logger.warning(
                        f"Failed to fetch tables for {catalog_name}.{schema_name}: {e}"
                    )
                    continue
                if tables:
                    yield tables

    async def create_webhook_destination_if_not_exists(self, url: str) -> None:
        """Idempotently creates a Databricks notification destination of type webhook
        pointing at `url`, used as the target for job run notifications. If a
        destination with the expected name already exists but points at a different
        URL (e.g. the integration's public host changed), it's recreated so
        Databricks keeps posting to the right place.
        """
        data = await self._get(NOTIFICATION_DESTINATIONS_ENDPOINT)
        destinations = data.get("results") or []
        for destination in destinations:
            if destination.get("display_name") != WEBHOOK_DESTINATION_NAME:
                continue

            destination_id = destination["id"]
            full_destination = await self._get(
                f"{NOTIFICATION_DESTINATIONS_ENDPOINT}/{destination_id}"
            )
            existing_url = (
                full_destination.get("config", {}).get("generic_webhook", {}).get("url")
            )
            if existing_url == url:
                logger.info(
                    "Databricks webhook notification destination already exists and is up to date, skipping creation"
                )
                return

            logger.info(
                "Databricks webhook notification destination URL changed, recreating it"
            )
            await self._send_api_request(
                f"{NOTIFICATION_DESTINATIONS_ENDPOINT}/{destination_id}",
                method="DELETE",
            )
            break

        body = {
            "display_name": WEBHOOK_DESTINATION_NAME,
            "config": {"generic_webhook": {"url": url}},
        }
        try:
            await self._send_api_request(
                NOTIFICATION_DESTINATIONS_ENDPOINT, method="POST", json_data=body
            )
            logger.info("Created Databricks webhook notification destination")
        except (httpx.HTTPStatusError, httpx.HTTPError) as e:
            logger.error(
                f"Error creating Databricks webhook notification destination: {e}"
            )
            raise
