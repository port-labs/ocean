from typing import Any

from loguru import logger
from azure_devops.client.azure_devops_client import AzureDevopsClient
from azure_devops.webhooks.webhook_processors.base_processor import (
    AzureDevOpsBaseWebhookProcessor,
)
from port_ocean.core.handlers.port_app_config.models import ResourceConfig
from port_ocean.core.handlers.webhook.webhook_event import (
    EventPayload,
    WebhookEvent,
    WebhookEventRawResults,
)
from azure_devops.misc import Kind
from azure_devops.webhooks.events import PipelineEvents, PushEvents
from integration import AzureDevopsPipelineResourceConfig

# Common pipeline YAML file patterns to detect pipeline definition changes
PIPELINE_YAML_PATTERNS = [
    "azure-pipelines.yml",
    "azure-pipelines.yaml",
    ".azure-pipelines/",
    "**/*azure-pipelines*.yml",
    "**/*azure-pipelines*.yaml",
]


class PipelineWebhookProcessor(AzureDevOpsBaseWebhookProcessor):
    async def get_matching_kinds(self, event: WebhookEvent) -> list[str]:
        return [Kind.PIPELINE]

    async def validate_payload(self, payload: EventPayload) -> bool:
        if not await super().validate_payload(payload):
            return False

        event_type = payload["eventType"]
        resource = payload["resource"]

        # For build events, validate essential fields needed to fetch pipeline
        if event_type == PipelineEvents.BUILD_COMPLETED:
            return bool(resource.get("id") and resource.get("definition"))

        # For push events, validate essential fields needed to check for YAML changes
        if event_type == PushEvents.PUSH:
            repository = resource.get("repository", {})
            return bool(repository.get("id") and resource.get("refUpdates"))

        return False

    async def should_process_event(self, event: WebhookEvent) -> bool:
        try:
            event_type = event.payload["eventType"]
            if event_type == PipelineEvents.BUILD_COMPLETED:
                return True
            if event_type == PushEvents.PUSH:
                return await self._has_pipeline_yaml_changes(event.payload)
            return False
        except (KeyError, ValueError):
            return False

    async def _has_pipeline_yaml_changes(self, payload: EventPayload) -> bool:
        """Check if push event contains changes to pipeline YAML files."""
        try:
            resource = payload.get("resource", {})
            ref_updates = resource.get("refUpdates", [])

            if not ref_updates:
                return False

            client = AzureDevopsClient.create_from_ocean_config()
            repository = resource.get("repository", {})
            repo_id = repository.get("id")
            project = repository.get("project", {})
            project_id = project.get("id")

            if not repo_id or not project_id:
                logger.debug(
                    f"Missing repository or project info: repo_id={repo_id}, project_id={project_id}"
                )
                return False

            # Check each ref update for pipeline YAML changes
            for ref_update in ref_updates:
                commit_id = ref_update.get("newObjectId")
                if not commit_id:
                    continue

                # Get commit changes
                try:
                    changes_response = await client.get_commit_changes(
                        project_id, repo_id, commit_id
                    )
                    if not changes_response:
                        continue

                    changed_files = changes_response.get("changes", [])
                    for changed_file in changed_files:
                        file_path = changed_file.get("item", {}).get("path", "").lower()
                        # Check if any changed file matches pipeline YAML patterns
                        if any(
                            pattern.lower() in file_path or file_path.endswith(pattern)
                            for pattern in PIPELINE_YAML_PATTERNS
                        ):
                            logger.info(
                                f"Detected pipeline YAML file change: {file_path} in repository {repo_id}"
                            )
                            return True
                except (KeyError, ValueError) as e:
                    logger.debug(
                        f"Error checking commit changes for commit {commit_id}: {e}"
                    )
                    continue

            return False
        except (KeyError, ValueError) as e:
            logger.error(
                f"Error checking for pipeline YAML changes in payload: {e}",
                exc_info=True,
            )
            return False

    async def handle_event(
        self, payload: EventPayload, resource_config: ResourceConfig
    ) -> WebhookEventRawResults:
        client = AzureDevopsClient.create_from_ocean_config()
        event_type = payload["eventType"]
        resource = payload["resource"]
        if event_type == PushEvents.PUSH:
            return await self._handle_pipeline_yaml_change_event(
                payload, resource_config, client
            )

        try:
            project = resource["project"]
            project_id = project["id"]
            definition = resource["definition"]
            pipeline_id = definition["id"]

            # Try to fetch the pipeline using the pipelines API (for YAML pipelines)
            pipeline_response = await self._fetch_pipeline_from_pipelines_api(
                client, project_id, pipeline_id
            )
            if pipeline_response:
                pipeline_response["__projectId"] = project_id
                pipeline_response = await self._enrich_pipeline_with_repository(
                    client, resource_config, pipeline_response
                )
                return WebhookEventRawResults(
                    updated_raw_results=[pipeline_response], deleted_raw_results=[]
                )

            logger.debug(
                f"Pipeline not found via pipelines API, trying build definitions API for definition {pipeline_id}"
            )
            pipeline_response = await self._fetch_pipeline_from_build_definitions_api(
                client, project_id, pipeline_id, definition
            )
            if pipeline_response:
                pipeline_response = await self._enrich_pipeline_with_repository(
                    client, resource_config, pipeline_response
                )
                return WebhookEventRawResults(
                    updated_raw_results=[pipeline_response], deleted_raw_results=[]
                )

            logger.warning(
                f"Pipeline/Build definition with ID {pipeline_id} not found in project {project_id}"
            )
            return WebhookEventRawResults(
                updated_raw_results=[], deleted_raw_results=[]
            )

        except (KeyError, ValueError) as e:
            logger.error(
                f"Error processing pipeline webhook event: {e}",
                exc_info=True,
            )
            return WebhookEventRawResults(
                updated_raw_results=[], deleted_raw_results=[]
            )
        except Exception as e:
            logger.error(
                f"Unexpected error processing pipeline webhook event: {e}",
                exc_info=True,
            )
            return WebhookEventRawResults(
                updated_raw_results=[], deleted_raw_results=[]
            )

    async def _fetch_pipeline_from_pipelines_api(
        self, client: AzureDevopsClient, project_id: str, pipeline_id: int
    ) -> dict[str, Any] | None:
        """Fetch pipeline from Azure DevOps Pipelines API."""
        pipeline_url = f"{client._organization_base_url}/{project_id}/_apis/pipelines/{pipeline_id}"
        pipeline_response_obj = await client.send_request("GET", pipeline_url)
        if pipeline_response_obj:
            return pipeline_response_obj.json()
        return None

    async def _fetch_pipeline_from_build_definitions_api(
        self,
        client: AzureDevopsClient,
        project_id: str,
        pipeline_id: int,
        definition: dict[str, Any],
    ) -> dict[str, Any] | None:
        """Fetch pipeline from Azure DevOps Build Definitions API."""
        build_def_url = f"{client._organization_base_url}/{project_id}/_apis/build/definitions/{pipeline_id}"
        build_def_response_obj = await client.send_request("GET", build_def_url)
        if build_def_response_obj:
            build_definition = build_def_response_obj.json()
            return {
                "id": str(build_definition.get("id", pipeline_id)),
                "name": build_definition.get(
                    "name", definition.get("name", "Unknown Pipeline")
                ),
                "__projectId": project_id,
            }
        return None

    async def _enrich_pipeline_with_repository(
        self,
        client: AzureDevopsClient,
        resource_config: ResourceConfig,
        pipeline_response: dict[str, Any],
    ) -> dict[str, Any]:
        """Enrich pipeline with repository information if configured."""
        if (
            isinstance(resource_config, AzureDevopsPipelineResourceConfig)
            and resource_config.selector.include_repo
        ):
            pipelines = await client.enrich_pipelines_with_repository(
                [pipeline_response]
            )
            if pipelines:
                return pipelines[0]
        return pipeline_response

    async def _handle_pipeline_yaml_change_event(
        self,
        payload: EventPayload,
        resource_config: ResourceConfig,
        client: AzureDevopsClient,
    ) -> WebhookEventRawResults:
        """Handle push events that contain pipeline YAML file changes."""
        try:
            resource = payload["resource"]
            repository = resource["repository"]
            repo_id = repository["id"]
            project = repository["project"]
            project_id = project["id"]

            logger.info(
                f"Processing pipeline YAML change for repository {repository['name']} in project {project_id}"
            )

            # Fetch pipelines for the project
            pipelines = await self._fetch_pipelines_for_project(client, project_id)
            if not pipelines:
                return WebhookEventRawResults(
                    updated_raw_results=[], deleted_raw_results=[]
                )

            # Filter pipelines by repository
            updated_pipelines = self._filter_pipelines_by_repository(
                pipelines, repo_id, project_id
            )

            # If no direct repository link, try build definitions
            if not updated_pipelines:
                updated_pipelines = await self._fetch_build_definitions_by_repository(
                    client, project_id, repo_id
                )

            # Enrich pipelines with repository if configured
            updated_pipelines = await self._enrich_pipelines_with_repository(
                client, resource_config, updated_pipelines
            )

            if updated_pipelines:
                logger.info(
                    f"Found {len(updated_pipelines)} pipeline(s) to update for repository {repository['name']}"
                )

            return WebhookEventRawResults(
                updated_raw_results=updated_pipelines, deleted_raw_results=[]
            )

        except (KeyError, ValueError) as e:
            logger.error(
                f"Error processing pipeline YAML change event: {e}", exc_info=True
            )
            return WebhookEventRawResults(
                updated_raw_results=[], deleted_raw_results=[]
            )

    async def _fetch_pipelines_for_project(
        self, client: AzureDevopsClient, project_id: str
    ) -> list[dict[str, Any]]:
        """Fetch all pipelines for a project."""
        pipelines_url = f"{client._organization_base_url}/{project_id}/_apis/pipelines"
        pipelines_response = await client.send_request("GET", pipelines_url)

        if (
            not pipelines_response
            or (pipelines := pipelines_response.json().get("value")) is None
        ):
            logger.info(f"No pipelines found for project {project_id}")
            return []
        return pipelines

    def _filter_pipelines_by_repository(
        self, pipelines: list[dict[str, Any]], repo_id: str, project_id: str
    ) -> list[dict[str, Any]]:
        """Filter pipelines that are associated with a repository."""
        updated_pipelines = []
        for pipeline in pipelines:
            pipeline_repo = pipeline.get("repository", {})
            if pipeline_repo.get("id") == repo_id:
                pipeline["__projectId"] = project_id
                updated_pipelines.append(pipeline)
        return updated_pipelines

    async def _fetch_build_definitions_by_repository(
        self, client: AzureDevopsClient, project_id: str, repo_id: str
    ) -> list[dict[str, Any]]:
        """Fetch build definitions linked to a repository."""
        logger.debug(
            f"No pipelines directly linked to repository {repo_id}, checking build definitions"
        )
        build_defs_url = (
            f"{client._organization_base_url}/{project_id}/_apis/build/definitions"
        )
        build_defs_response = await client.send_request("GET", build_defs_url)

        if not build_defs_response:
            return []

        build_defs = build_defs_response.json().get("value", [])
        return [
            {
                "id": str(build_def.get("id", "")),
                "name": build_def.get("name", "Unknown Pipeline"),
                "__projectId": project_id,
            }
            for build_def in build_defs
            if build_def.get("repository", {}).get("id") == repo_id
        ]

    async def _enrich_pipelines_with_repository(
        self,
        client: AzureDevopsClient,
        resource_config: ResourceConfig,
        pipelines: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        """Enrich pipelines with repository information if configured."""
        if (
            isinstance(resource_config, AzureDevopsPipelineResourceConfig)
            and resource_config.selector.include_repo
        ):
            return await client.enrich_pipelines_with_repository(pipelines)
        return pipelines
