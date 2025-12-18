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


class PipelineWebhookProcessor(AzureDevOpsBaseWebhookProcessor):
    async def get_matching_kinds(self, event: WebhookEvent) -> list[str]:
        return [Kind.PIPELINE]

    async def validate_payload(self, payload: EventPayload) -> bool:
        if not await super().validate_payload(payload):
            return False

        event_type = payload.get("eventType", "")
        resource = payload.get("resource", {})

        # For build events, validate build resource structure
        if event_type in [PipelineEvents.BUILD_COMPLETED, PipelineEvents.BUILD_STARTED]:
            return bool(resource.get("id") and resource.get("definition"))

        # For push events, validate repository structure
        if event_type == PushEvents.PUSH:
            repository = resource.get("repository", {})
            ref_updates = resource.get("refUpdates")
            return bool(repository.get("id") and repository.get("name") and ref_updates)

        return False

    async def should_process_event(self, event: WebhookEvent) -> bool:
        try:
            event_type = event.payload["eventType"]
            # Handle build events (existing functionality)
            if PipelineEvents(event_type):
                return True
            # Handle push events for pipeline YAML changes (new functionality)
            if PushEvents(event_type):
                return await self._has_pipeline_yaml_changes(event.payload)
            return False
        except ValueError:
            return False

    async def _has_pipeline_yaml_changes(self, payload: EventPayload) -> bool:
        """Check if push event contains changes to pipeline YAML files."""
        try:
            resource = payload.get("resource", {})
            ref_updates = resource.get("refUpdates", [])

            if not ref_updates:
                return False

            # Common pipeline YAML file patterns
            pipeline_patterns = [
                "azure-pipelines.yml",
                "azure-pipelines.yaml",
                ".azure-pipelines/",
                "**/*azure-pipelines*.yml",
                "**/*azure-pipelines*.yaml",
            ]

            client = AzureDevopsClient.create_from_ocean_config()
            repository = resource.get("repository", {})
            repo_id = repository.get("id")
            project = repository.get("project", {})
            project_id = project.get("id")

            if not repo_id or not project_id:
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
                            for pattern in pipeline_patterns
                        ):
                            logger.info(
                                f"Detected pipeline YAML file change: {file_path}"
                            )
                            return True
                except Exception as e:
                    logger.debug(f"Error checking commit changes: {e}")
                    continue

            return False
        except Exception as e:
            logger.error(f"Error checking for pipeline YAML changes: {e}")
            return False

    async def handle_event(
        self, payload: EventPayload, resource_config: ResourceConfig
    ) -> WebhookEventRawResults:
        client = AzureDevopsClient.create_from_ocean_config()
        event_type = payload.get("eventType", "")
        resource = payload["resource"]

        # Handle push events for pipeline YAML changes
        if event_type == PushEvents.PUSH:
            return await self._handle_pipeline_yaml_change_event(
                payload, resource_config, client
            )

        # Handle build events (existing functionality)
        build_id = resource.get("id")
        definition = resource.get("definition", {})

        if not build_id or not definition:
            logger.warning(
                f"Pipeline webhook payload missing required fields: build_id={build_id}, definition={definition}"
            )
            return WebhookEventRawResults(
                updated_raw_results=[], deleted_raw_results=[]
            )

        try:
            # Extract project and pipeline information from the build resource
            project = resource.get("project", {})
            project_id = project.get("id")
            definition = resource.get("definition", {})
            pipeline_id = definition.get("id")

            if not project_id or not pipeline_id:
                logger.warning(
                    f"Missing project_id or pipeline_id in webhook payload: project_id={project_id}, pipeline_id={pipeline_id}"
                )
                return WebhookEventRawResults(
                    updated_raw_results=[], deleted_raw_results=[]
                )

            # Try to fetch the pipeline using the pipelines API (for YAML pipelines)
            pipeline_url = (
                f"{client._organization_base_url}/{project_id}/_apis/pipelines/{pipeline_id}"
            )
            pipeline_response_obj = await client.send_request("GET", pipeline_url)

            if pipeline_response_obj:
                pipeline_response = pipeline_response_obj.json()
                # Add project context to pipeline
                pipeline_response["__projectId"] = project_id

                # If the resource config includes repository enrichment, fetch it
                from integration import AzureDevopsPipelineResourceConfig

                if isinstance(resource_config, AzureDevopsPipelineResourceConfig):
                    if resource_config.selector.include_repo:
                        pipelines = await client.enrich_pipelines_with_repository(
                            [pipeline_response]
                        )
                        if pipelines:
                            pipeline_response = pipelines[0]

                return WebhookEventRawResults(
                    updated_raw_results=[pipeline_response], deleted_raw_results=[]
                )

            # If pipelines API fails, try build definitions API (for classic builds)
            # Note: This converts classic build definitions to pipeline format
            logger.debug(
                f"Pipeline not found via pipelines API, trying build definitions API for definition {pipeline_id}"
            )
            build_def_url = (
                f"{client._organization_base_url}/{project_id}/_apis/build/definitions/{pipeline_id}"
            )
            build_def_response_obj = await client.send_request("GET", build_def_url)

            if build_def_response_obj:
                build_definition = build_def_response_obj.json()
                # Convert build definition to pipeline format
                pipeline_response = {
                    "id": str(build_definition.get("id", pipeline_id)),
                    "name": build_definition.get("name", definition.get("name", "Unknown Pipeline")),
                    "__projectId": project_id,
                }

                # If the resource config includes repository enrichment, fetch it
                from integration import AzureDevopsPipelineResourceConfig

                if isinstance(resource_config, AzureDevopsPipelineResourceConfig):
                    if resource_config.selector.include_repo:
                        pipelines = await client.enrich_pipelines_with_repository(
                            [pipeline_response]
                        )
                        if pipelines:
                            pipeline_response = pipelines[0]

                return WebhookEventRawResults(
                    updated_raw_results=[pipeline_response], deleted_raw_results=[]
                )

            logger.warning(
                f"Pipeline/Build definition with ID {pipeline_id} not found in project {project_id}"
            )
            return WebhookEventRawResults(
                updated_raw_results=[], deleted_raw_results=[]
            )

        except Exception as e:
            logger.error(f"Error processing pipeline webhook event: {e}")
            return WebhookEventRawResults(
                updated_raw_results=[], deleted_raw_results=[]
            )

    async def _handle_pipeline_yaml_change_event(
        self,
        payload: EventPayload,
        resource_config: ResourceConfig,
        client: AzureDevopsClient,
    ) -> WebhookEventRawResults:
        """Handle push events that contain pipeline YAML file changes."""
        try:
            resource = payload["resource"]
            repository = resource.get("repository", {})
            repo_id = repository.get("id")
            project = repository.get("project", {})
            project_id = project.get("id")

            if not repo_id or not project_id:
                logger.warning(
                    f"Missing repository or project info: repo_id={repo_id}, project_id={project_id}"
                )
                return WebhookEventRawResults(
                    updated_raw_results=[], deleted_raw_results=[]
                )

            logger.info(
                f"Processing pipeline YAML change for repository {repository.get('name')} in project {project_id}"
            )

            # Fetch all pipelines for the project
            pipelines_url = (
                f"{client._organization_base_url}/{project_id}/_apis/pipelines"
            )
            pipelines_response = await client.send_request("GET", pipelines_url)

            if not pipelines_response:
                logger.warning(f"Could not fetch pipelines for project {project_id}")
                return WebhookEventRawResults(
                    updated_raw_results=[], deleted_raw_results=[]
                )

            pipelines_data = pipelines_response.json()
            pipelines = pipelines_data.get("value", [])

            if not pipelines:
                logger.info(f"No pipelines found for project {project_id}")
                return WebhookEventRawResults(
                    updated_raw_results=[], deleted_raw_results=[]
                )

            # Filter pipelines that are associated with this repository
            updated_pipelines = []
            for pipeline in pipelines:
                # Check if pipeline is linked to the repository
                # For YAML pipelines, check repository property
                pipeline_repo = pipeline.get("repository", {})
                if pipeline_repo.get("id") == repo_id:
                    pipeline["__projectId"] = project_id
                    updated_pipelines.append(pipeline)

            # If no direct repository link, try to get pipelines via build definitions
            if not updated_pipelines:
                logger.debug(
                    f"No pipelines directly linked to repository {repo_id}, checking build definitions"
                )
                # Fetch build definitions that might be linked to this repository
                build_defs_url = (
                    f"{client._organization_base_url}/{project_id}/_apis/build/definitions"
                )
                build_defs_response = await client.send_request("GET", build_defs_url)

                if build_defs_response:
                    build_defs_data = build_defs_response.json()
                    build_defs = build_defs_data.get("value", [])

                    for build_def in build_defs:
                        build_def_repo = build_def.get("repository", {})
                        if build_def_repo.get("id") == repo_id:
                            # Convert build definition to pipeline format
                            pipeline_response = {
                                "id": str(build_def.get("id", "")),
                                "name": build_def.get("name", "Unknown Pipeline"),
                                "__projectId": project_id,
                            }
                            updated_pipelines.append(pipeline_response)

            # Enrich pipelines with repository if configured
            from integration import AzureDevopsPipelineResourceConfig

            if isinstance(resource_config, AzureDevopsPipelineResourceConfig):
                if resource_config.selector.include_repo:
                    updated_pipelines = await client.enrich_pipelines_with_repository(
                        updated_pipelines
                    )

            if updated_pipelines:
                logger.info(
                    f"Found {len(updated_pipelines)} pipeline(s) to update for repository {repository.get('name')}"
                )

            return WebhookEventRawResults(
                updated_raw_results=updated_pipelines, deleted_raw_results=[]
            )

        except Exception as e:
            logger.error(f"Error processing pipeline YAML change event: {e}")
            return WebhookEventRawResults(
                updated_raw_results=[], deleted_raw_results=[]
            )
