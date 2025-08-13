from port_ocean.utils import http_async_client
import httpx
from typing import Any, AsyncGenerator, Dict, List, Optional, Union
from loguru import logger
from enum import StrEnum
import asyncio
from port_ocean.utils.cache import cache_iterator_result
from port_ocean.utils.async_iterators import stream_async_iterators_tasks
from port_ocean.context.ocean import ocean


PAGE_SIZE = 100


class ObjectKind(StrEnum):
    PROJECT = "project"
    AUDITLOG = "auditlog"
    FEATURE_FLAG = "flag"
    ENVIRONMENT = "environment"
    FEATURE_FLAG_STATUS = "flag-status"
    FEATURE_FLAG_DEPENDENCY = "flag-dependency"


class LaunchDarklyClient:
    def __init__(
        self, api_token: str, launchdarkly_url: str, webhook_secret: str | None = None
    ):
        self.api_url = f"{launchdarkly_url}/api/v2"
        self.api_token = api_token
        self.http_client = http_async_client
        self.http_client.headers.update(self.api_auth_header)
        self.webhook_secret = webhook_secret

    @property
    def api_auth_header(self) -> dict[str, Any]:
        return {
            "Authorization": f"{self.api_token}",
            "Content-Type": "application/json",
        }

    @classmethod
    def create_from_ocean_configuration(cls) -> "LaunchDarklyClient":
        logger.info(f"Initializing LaunchDarklyClient {ocean.integration_config}")
        return LaunchDarklyClient(
            launchdarkly_url=ocean.integration_config["launchdarkly_host"],
            api_token=ocean.integration_config["launchdarkly_token"],
            webhook_secret=ocean.integration_config["webhook_secret"],
        )

    async def get_paginated_resource(
        self, kind: str, resource_path: str | None = None, page_size: int = PAGE_SIZE
    ) -> AsyncGenerator[list[dict[str, Any]], None]:
        """
        Fetch and paginate through resources from a LaunchDarkly API endpoint.
        Docs: https://launchdarkly.com/docs/guides/api/api-migration-guide#working-with-paginated-endpoints
        """
        kind = f"{kind}s" if not kind.endswith("s") else f"{kind}es"

        url = kind if not resource_path else f"{kind}/{resource_path}"
        url = url.replace("auditlogs", ObjectKind.AUDITLOG)
        params: Optional[dict[str, Any]] = {"limit": page_size}

        while url:
            try:
                logger.debug(f"Fetching {kind} from LaunchDarkly: {url}")
                response = await self.send_api_request(
                    endpoint=url, query_params=params
                )
                items = response.get("items", [])
                logger.info(f"Received batch with {len(items)} items")
                yield items

                if next_link := response.get("_links", {}).get("next"):
                    url = next_link["href"]
                    logger.debug(f"Fetching next page of {kind}: {url}")
                    params = None
                else:
                    total_count = response.get("totalCount", len(items))
                    logger.info(
                        f"Successfully fetched all {total_count} {kind} from LaunchDarkly."
                    )
                    break

            except httpx.HTTPStatusError as e:
                logger.error(
                    f"HTTP error with status code: {e.response.status_code} and response text: {e.response.text}"
                )
                raise
            except httpx.HTTPError as e:
                logger.error(
                    f"HTTP error occurred while fetching {kind} from LaunchDarkly: {e}"
                )
                raise

    async def send_api_request(
        self,
        endpoint: str,
        method: str = "GET",
        query_params: Optional[dict[str, Any]] = None,
        json_data: Optional[Union[dict[str, Any], list[Any]]] = None,
        headers: Optional[dict[str, Any]] = None,
    ) -> dict[str, Any]:
        try:
            endpoint = endpoint.replace("/api/v2/", "")
            url = f"{self.api_url}/{endpoint}"
            logger.debug(
                f"URL: {url}, Method: {method}, Params: {query_params}, Body: {json_data}"
            )
            response = await self.http_client.request(
                method=method,
                url=url,
                params=query_params,
                json=json_data,
                headers=headers,
            )
            response.raise_for_status()

            return response.json()

        except httpx.HTTPStatusError as e:
            logger.error(
                f"HTTP error on {endpoint}: {e.response.status_code} - {e.response.text}"
            )
            raise
        except httpx.HTTPError as e:
            logger.error(f"HTTP error on {endpoint}: {str(e)}")
            raise

    @cache_iterator_result()
    async def get_paginated_projects(
        self,
    ) -> AsyncGenerator[list[dict[str, Any]], None]:
        async for projects in self.get_paginated_resource(ObjectKind.PROJECT):
            logger.info(f"Retrieved {len(projects)} projects from launchdarkly")
            yield projects

    @cache_iterator_result()
    async def get_paginated_environments(
        self,
    ) -> AsyncGenerator[list[dict[str, Any]], None]:
        async for projects in self.get_paginated_projects():
            tasks = [
                self.fetch_environments_for_project(project) for project in projects
            ]
            environments = await asyncio.gather(*tasks)
            for environment_batch in environments:
                yield environment_batch

    async def fetch_environments_for_project(
        self, project: dict[str, Any]
    ) -> list[dict[str, Any]]:
        environments = []
        async for environment_batch in self.get_paginated_resource(
            ObjectKind.PROJECT,
            resource_path=f'{project["key"]}/{ObjectKind.ENVIRONMENT}s',
        ):
            updated_batch = [
                {**environment, "__projectKey": project["key"]}
                for environment in environment_batch
            ]
            environments.extend(updated_batch)
        return environments

    async def get_feature_flag_status(
        self, projectKey: str, featureFlagKey: str
    ) -> dict[str, Any]:
        endpoint = f"flag-status/{projectKey}/{featureFlagKey}"
        feature_flag_status = await self.send_api_request(endpoint)
        return feature_flag_status

    async def get_paginated_feature_flag_statuses(
        self,
    ) -> AsyncGenerator[list[dict[str, Any]], None]:
        async for environments in self.get_paginated_environments():
            tasks = [
                self.fetch_statuses_from_environment(environment)
                for environment in environments
            ]
            async for resource_groups_batch in stream_async_iterators_tasks(*tasks):
                yield resource_groups_batch

    async def fetch_statuses_from_environment(
        self, environment: dict[str, Any]
    ) -> AsyncGenerator[list[dict[str, Any]], None]:
        resource = f"{environment['__projectKey']}/{environment['key']}"
        async for statuses in self.get_paginated_resource(
            kind=ObjectKind.FEATURE_FLAG_STATUS, resource_path=resource
        ):
            updated_batch = [
                {
                    **status,
                    "__environmentKey": environment["key"],
                    "__projectKey": environment["__projectKey"],
                }
                for status in statuses
            ]
            yield updated_batch

    async def get_paginated_feature_flags(
        self,
    ) -> AsyncGenerator[list[dict[str, Any]], None]:
        async for projects in self.get_paginated_projects():
            tasks = [
                self.fetch_feature_flags_for_project(project) for project in projects
            ]

            feature_flags_batches = await asyncio.gather(*tasks)
            for feature_flags in feature_flags_batches:
                yield feature_flags

    async def fetch_feature_flags_for_project(
        self, project: dict[str, Any]
    ) -> list[dict[str, Any]]:
        feature_flags = []
        async for flags_batch in self.get_paginated_resource(
            ObjectKind.FEATURE_FLAG, resource_path=project["key"]
        ):
            updated_batch = [
                {**flag, "__projectKey": project["key"]} for flag in flags_batch
            ]
            feature_flags.extend(updated_batch)
        return feature_flags

    async def patch_webhook(self, webhook_id: str, webhook_secret: str) -> None:
        """Patch a webhook to add a secret."""

        patch_data = [{"op": "replace", "path": "/secret", "value": webhook_secret}]

        logger.info(f"Patching webhook {webhook_id} to add secret")
        await self.send_api_request(
            endpoint=f"webhooks/{webhook_id}", method="PATCH", json_data=patch_data
        )
        logger.info(f"Successfully patched webhook {webhook_id} with secret")
    
    async def get_feature_flag_dependencies(
        self, projectKey: str, featureFlagKey: str
    ) -> list[dict[str, Any]]:
        endpoint = f"flags/{projectKey}/{featureFlagKey}/dependent-flags"
        logger.info(f"Fetching dependencies for {projectKey}/{featureFlagKey} from {endpoint}")
        
        #added beta header because the endpoint is not available in the stable version
        feature_flag_dependencies = await self.send_api_request(endpoint=endpoint, headers={"LD-API-Version": "beta"})
        logger.info(f"Received {len(feature_flag_dependencies)} dependencies for flag {featureFlagKey}")
        return feature_flag_dependencies.get("items", [])

    async def get_feature_flag_dependencies_by_environment(
        self, projectKey: str, featureFlagKey: str, environmentKey: str
    ) -> list[dict[str, Any]]:
        endpoint = f"flags/{projectKey}/{environmentKey}/{featureFlagKey}/dependent-flags"
        logger.info(f"Fetching dependencies for {projectKey}/{environmentKey}/{featureFlagKey} from {endpoint}")
        
        #added beta header because the endpoint is not available in the stable version
        feature_flag_dependencies = await self.send_api_request(endpoint=endpoint, headers={"LD-API-Version": "beta"})
        logger.info(f"Received {len(feature_flag_dependencies)} dependencies for flag {featureFlagKey}")
        return feature_flag_dependencies.get("items", [])
    
    @cache_iterator_result()
    async def get_paginated_feature_flag_dependencies(
        self,
    ) -> AsyncGenerator[List[Dict[str, Any]], None]:
        """
        Get dependencies for all feature flags across all projects and environments.
        Optimized with controlled concurrency and batching.
        """

        # Added this based on LaunchDarkly's rate limit & your network
        MAX_CONCURRENT_REQUESTS = 5
        sem = asyncio.Semaphore(MAX_CONCURRENT_REQUESTS)

        # Cache environments per project
        env_cache: Dict[str, List[Dict[str, Any]]] = {}

        async def fetch_env_dep(project_key: str, flag_key: str, env: Dict[str, Any]):
            """Fetch dependencies for a single environment with semaphore limit."""
            async with sem:
                deps = await self.get_feature_flag_dependencies_by_environment(
                    project_key, flag_key, env["key"]
                )
            enriched = []
            for dep in deps:
                if not dep.get("key"):
                    logger.warning(
                        f"Skipping dependency without key for {project_key}/{flag_key}/{env['key']}: {dep}"
                    )
                    continue
                enriched_dep = {}
                # Main flag info
                enriched_dep["flagKey"] = flag_key
                enriched_dep["projectKey"] = project_key

                # Dependent flag info
                enriched_dep["dependentFlagKey"] = dep["key"]
                enriched_dep["dependentFlagName"] = dep.get("name", "")
                enriched_dep["dependentProjectKey"] = project_key

                # Context info
                enriched_dep["environmentKey"] = env["key"]
                enriched_dep["relationshipType"] = dep.get("relationshipType", "is_depended_on_by")
                
                enriched.append(enriched_dep)
            return enriched

        async def fetch_flag_env_deps(project_key: str, flag: Dict[str, Any], environments: List[Dict[str, Any]]):
            """Fetch dependencies for all environments of a flag."""
            flag_key = flag["key"]
            results = await asyncio.gather(
                *(fetch_env_dep(project_key, flag_key, env) for env in environments)
            )
            # Flatten results
            return [dep for env_deps in results for dep in env_deps]

        async for projects in self.get_paginated_projects():
            for project in projects:
                project_key = project["key"]

                # Cache environments for this project
                if project_key not in env_cache:
                    env_cache[project_key] = await self.fetch_environments_for_project(project)

                environments = env_cache[project_key]

            # Get all feature flags for this project
            async for flags_batch in self.get_paginated_resource(
                ObjectKind.FEATURE_FLAG, resource_path=project_key
            ):
                if not flags_batch:
                    continue

                logger.info(f"Received {len(flags_batch)} feature flags for project {project_key}")

                # Process in batches
                batch_size = 10
                for i in range(0, len(flags_batch), batch_size):
                    batch = flags_batch[i:i + batch_size]

                    # Fetch dependencies for all flags in batch concurrently
                    deps_batches = await asyncio.gather(
                        *(fetch_flag_env_deps(project_key, flag, environments) for flag in batch)
                    )

                    # Flatten and yield only non-empty results
                    all_dependencies = [dep for deps in deps_batches for dep in deps if deps]
                    if all_dependencies:
                        yield all_dependencies

    
    async def _format_flag_dependencies(
        self, projectKey: str, featureFlagKey: str
    ) -> list[dict[str, Any]]:
        """Helper method to fetch and format dependencies for a specific flag.
        
        Note: This method is kept for backward compatibility but is no longer used by
        get_paginated_flag_dependencies, which now handles environment-specific dependencies.
        """
        try:
            logger.info(f"Fetching dependencies for flag {featureFlagKey}")
            dependent_flags = await self.get_feature_flag_dependencies(projectKey, featureFlagKey)
            logger.info(f"Received {len(dependent_flags)} dependencies for flag {featureFlagKey}")
            formatted = []
            # Handle the case where dependent_flags might be None
            if dependent_flags is None:
                return []
                
            # Now iterate through the iterable directly
            for dep in dependent_flags:
                dep_key = dep.get("key")
                if not dep_key:
                    logger.warning(f"Skipping dependency without key for {projectKey}/{featureFlagKey}: {dep}")
                    continue
                # Preserve original dependency data and only enrich with necessary fields
                enriched_dep = dep.copy()
                # Add required fields for entity identification
                enriched_dep["flagKey"] = featureFlagKey
                enriched_dep["__projectKey"] = projectKey
                # Ensure we have a relationship type if not already present
                if "relationshipType" not in enriched_dep:
                    enriched_dep["relationshipType"] = "is_depended_on_by"
                formatted.append(enriched_dep)
            return formatted
        except Exception as e:
            logger.error(f"Error fetching dependencies for {projectKey}/{featureFlagKey}: {e}")
            return []

    async def create_launchdarkly_webhook(self, base_url: str) -> None:
        """Create or update a webxhook in LaunchDarkly."""
        webhook_target_url = f"{base_url}/integration/webhook"
        logger.info(f"Checking for existing webhook at {webhook_target_url}")

        notifications_response = await self.send_api_request(endpoint="webhooks")
        existing_configs = notifications_response.get("items", [])

        existing_webhook = next(
            (
                config
                for config in existing_configs
                if config["url"] == webhook_target_url
            ),
            None,
        )

        if not existing_webhook:
            logger.info("Creating new webhook")
            webhook_body = {
                "url": webhook_target_url,
                "description": "Port Integration Webhook",
                "sign": bool(self.webhook_secret),
                "secret": self.webhook_secret,
            }
            await self.send_api_request(
                endpoint="webhooks", method="POST", json_data=webhook_body
            )
            logger.info("Successfully created new webhook")
            return

        logger.info(f"Found existing webhook with ID: {existing_webhook['_id']}")

        if self.webhook_secret and not existing_webhook.get("secret"):
            logger.info("Existing webhook has no secret, adding one")
            await self.patch_webhook(existing_webhook["_id"], self.webhook_secret)
            return

        logger.info("Webhook already exists with appropriate configuration")
