import asyncio
import aiolimiter
from loguru import logger
from port_ocean.context.ocean import ocean
from port_ocean.utils import http_async_client
from core.utils import parse_datetime, generate_entity_from_port_yaml, load_mappings
from core.async_fetcher import AsyncFetcher
from gitlab.v4.objects import Project

class KindNotImplementedException(Exception):
    def __init__(self, kind: str, available_kinds: list[str]):
        self.kind = kind
        self.available_kinds = available_kinds
        super().__init__(f"Unsupported kind: {kind}. Available kinds: {', '.join(available_kinds)}")

    def __reduce__(self):
        return (self.__class__, (self.kind, self.available_kinds))

class GitLabHandler:
    def __init__(self) -> None:
        self.token = ocean.integration_config.get("gitlab_token")
        self.gitlab_baseurl = ocean.integration_config.get("gitlab_url")
        self.port_url = ocean.config.port.base_url
        self.client = http_async_client
        self.headers = {"Authorization": f"Bearer {self.token}"}
        self.rate_limiter = aiolimiter.AsyncLimiter(
            max_rate=10  # Adjust based on GitLab rate limits
        )

        # Load mappings from port-app-config.yml
        self.mappings = load_mappings(".port/resources/port-app-config.yml")

    async def fetch_data(self, endpoint: str, params: dict = None) -> list:
        url = f"{self.gitlab_baseurl}{endpoint}"
        async for page in self.paginated_fetch(url, params):
            yield page

    async def paginated_fetch(self, url: str, params: dict = None) -> list:
        params = params or {}
        params["per_page"] = 100  # Adjust based on GitLab API
        params["page"] = 1

        while True:
            async with self.rate_limiter:
                resp = await self.client.get(url, headers=self.headers, params=params)
                if resp.status_code == 429:  # Rate Limiting
                    message = resp.json().get("message", "")
                    logger.error(f"{message}, retry will start in 5 minutes.")
                    await asyncio.sleep(300)  # Sleep for 5 minutes
                    continue

                if resp.status_code != 200:
                    logger.error(
                        f"Encountered an HTTP error with status code: {resp.status_code} and response text: {resp.text} while calling {url}"
                    )
                    return  # Use return without a value to indicate the end of the generator

                data = resp.json()
                if not data:
                    return  # Use return without a value to indicate the end of the generator

                yield data
                params["page"] += 1

    async def patch_entity(
        self, blueprint_identifier: str, entity_identifier: str, payload: dict
    ):
        port_headers = await ocean.port_client.auth.headers()
        url = f"{self.port_url}/v1/blueprints/{blueprint_identifier}/entities/{entity_identifier}"
        resp = await self.client.put(url, json=payload, headers=port_headers)
        if resp.status_code != 200:
            logger.error(
                f"Error Upserting entity: {entity_identifier} of blueprint: {blueprint_identifier}"
            )
            logger.error(
                f"Request failed with status code: {resp.status_code}, Error: {resp.text}"
            )

        return resp.json()

    async def generic_handler(self, data: dict, kind: str) -> None:
        if kind not in self.mappings:
            available_kinds = list(self.mappings.keys())
            raise KindNotImplementedException(kind, available_kinds)

        # Create a raw entity dictionary
        raw_entity = {
            "identifier": jq.compile(self.mappings[kind]["identifier"]).input(data).first(),
            "title": jq.compile(self.mappings[kind]["title"]).input(data).first(),
            "blueprint": self.mappings[kind]["blueprint"],
            "properties": data,
            "relations": data,
        }

        # Map data using the generate_entity_from_port_yaml method
        project_id = jq.compile(self.mappings[kind]["relations"].get("service", "")).input(data).first() if "relations" in self.mappings[kind] else None
        if project_id:
            project = await self.fetch_project(project_id)
            ref = "main"  # Adjust the ref as needed
            payload = await generate_entity_from_port_yaml(raw_entity, project, ref, self.mappings[kind])
        else:
            payload = raw_entity

        payload["properties"]["createdAt"] = await parse_datetime(payload["properties"]["createdAt"])
        payload["properties"]["updatedAt"] = await parse_datetime(payload["properties"]["updatedAt"])

        logger.debug(f"Payload before upsert: {payload}")
        await self.patch_entity(payload["blueprint"], payload["identifier"], payload)

    async def fetch_project(self, project_id: str) -> Project:
        gitlab_url = ocean.integration_config.get("gitlab_url")
        token = ocean.integration_config.get("gitlab_token")
        gitlab = await AsyncFetcher.get_gitlab_client(gitlab_url, token)
        return gitlab.projects.get(project_id)

    async def webhook_handler(self, data: dict) -> None:
        object_kind = data["object_kind"]
        await self.generic_handler(data, object_kind)

    async def system_hook_handler(self, data: dict) -> None:
        event_name = data["event_name"]
        if event_name in [
            "project_create",
            "project_destroy",
            "project_rename",
            "project_update",
        ]:
            await self.generic_handler(data, "project")
        elif event_name in ["group_create", "group_destroy", "group_rename"]:
            await self.generic_handler(data, "gitlabGroup")