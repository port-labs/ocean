import asyncio
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, TypedDict, cast

import httpx
from loguru import logger
from github.core.exporters.file_exporter.utils import (
    FileObject,
)
from integration import GithubFileResourceConfig, GithubFilePattern, GithubPortAppConfig
from port_ocean.clients.port.types import RequestOptions
from port_ocean.context.ocean import ocean
from port_ocean.core.models import Entity
from port_ocean.core.handlers.entity_processor import JQEntityProcessor
from port_ocean.core.integrations.mixins.utils import handle_items_to_parse
from datetime import datetime, timezone
from github.clients.client_factory import create_github_client_for_org
from github.helpers.exceptions import CheckRunsException

MAX_CONCURRENT_ITEM_VALIDATIONS = 10
# GitHub rejects check run output text longer than 65535 characters.
MAX_REPORTED_ITEM_ERRORS = 10


class ValidationResult(TypedDict):
    success: bool
    errors: List[str]
    response: Optional[Any]


@dataclass
class ResourceConfigToPatternMapping:
    resource_config: GithubFileResourceConfig
    patterns: List[GithubFilePattern]


@dataclass
class MatchedFile:
    resource_config: GithubFileResourceConfig
    file_info: Dict[str, Any]


def _format_port_http_error(error: httpx.HTTPStatusError) -> str:
    """Extract the Port API error message from an HTTP error response."""
    try:
        body = error.response.json()
    except Exception:
        body = None

    if isinstance(body, dict):
        message = body.get("message") or body.get("error")
        if message:
            return str(message)

    text = error.response.text
    if text:
        return text
    return str(error)


class CheckRuns:
    """Handles GitHub check run operations for file validation."""

    async def create_validation_check(
        self, organization: str, repo_name: str, head_sha: str
    ) -> str:
        """Create a new check run for validation."""
        client = await create_github_client_for_org(organization)
        endpoint = f"{client.base_url}/repos/{organization}/{repo_name}/check-runs"

        payload = {
            "name": "File Kind validation",
            "head_sha": head_sha,
            "status": "in_progress",
            "output": {
                "title": "Validating file kind changes",
                "summary": "Checking if file kind changes are valid according to Port configuration.",
            },
        }

        response = await client.send_api_request(
            endpoint, method="POST", json_data=payload
        )
        if not response:
            log_message = f"Failed to create check run for {repo_name} of organization: {organization}"
            logger.error(log_message)
            raise CheckRunsException(log_message)

        check_run_id = response["id"]

        logger.info(
            f"Created check run {check_run_id} for {repo_name} of organization: {organization}"
        )

        return str(check_run_id)

    async def update_check_run(
        self,
        organization: str,
        repo_name: str,
        check_run_id: str,
        status: str,
        conclusion: str,
        title: str,
        summary: str,
        details: str,
    ) -> None:
        """Update check run with results."""
        client = await create_github_client_for_org(organization)
        endpoint = f"{client.base_url}/repos/{organization}/{repo_name}/check-runs/{check_run_id}"

        payload = {
            "status": status,
            "conclusion": conclusion,
            "completed_at": datetime.now(timezone.utc).isoformat(),
            "output": {"title": title, "summary": summary, "text": details},
        }

        await client.send_api_request(endpoint, method="PATCH", json_data=payload)

        logger.info(
            f"Updated check run {check_run_id} for {repo_name} with {conclusion} status of organization: {organization}"
        )


class FileValidationService:
    """Service for validating files during pull request processing."""

    def __init__(self, organization: str) -> None:
        self.organization = organization
        self.check_runs = CheckRuns()
        self._validation_semaphore = asyncio.Semaphore(MAX_CONCURRENT_ITEM_VALIDATIONS)

    async def validate_pull_request_files(
        self,
        changed_file: FileObject,
        resource_config: GithubFileResourceConfig,
        head_sha: str,
        pr_number: int,
    ) -> None:
        """Validate files in a pull request against Port configuration."""

        repo_name = changed_file["repository"]["name"]
        file_path = changed_file["path"]

        logger.info(
            f"Starting validation for file {file_path} in PR {repo_name}/{pr_number} of organization: {self.organization}"
        )

        validation_check_status = "completed"
        validation_check_conclusion = "success"
        validation_check_title = "File validation passed"
        validation_check_summary = "Successfully validated file"
        validation_check_details = "All files passed validation"

        try:
            check_run_id = await self.check_runs.create_validation_check(
                organization=self.organization, repo_name=repo_name, head_sha=head_sha
            )
        except Exception as e:
            logger.error(
                f"Failed to create validation check: {str(e)} of organization: {self.organization}"
            )
            return

        try:
            validation_errors = []
            result: ValidationResult = await self._validate_file_against_port(
                changed_file, resource_config
            )

            logger.info(
                f"Validation result {'success' if result['success'] else 'failure'} for file {file_path} of organization: {self.organization}"
            )

            if not result["success"]:
                error_msg = f"Validation failed for {file_path}: {', '.join(result['errors'])} of organization: {self.organization}"
                validation_errors.append(error_msg)

            if validation_errors:
                validation_check_conclusion = "failure"
                validation_check_title = "File validation failed"
                validation_check_summary = (
                    f"Found {len(validation_errors)} validation errors"
                )
                validation_check_details = "\n".join(validation_errors)

        except Exception as e:
            logger.error(
                f"Validation error: {str(e)} of organization: {self.organization}"
            )
            validation_check_conclusion = "failure"
            validation_check_title = "File validation error"
            validation_check_summary = "An error occurred during validation"
            validation_check_details = str(e)

        await self.check_runs.update_check_run(
            self.organization,
            repo_name,
            check_run_id,
            validation_check_status,
            validation_check_conclusion,
            validation_check_title,
            validation_check_summary,
            validation_check_details,
        )

    async def _expand_items(
        self,
        file: FileObject,
        resource_config: GithubFileResourceConfig,
        items_to_parse: str,
        jq_processor: JQEntityProcessor,
    ) -> tuple[List[Dict[str, Any]], Optional[str]]:
        """Raw items sync would map. An empty list is valid; a non-list is an error."""
        raw_items = [
            item
            async for batch in handle_items_to_parse(
                [dict(file)],
                resource_config.port.items_to_parse_name,
                items_to_parse,
                resource_config.port.items_to_parse_top_level_transform,
            )
            for item in batch
        ]
        if raw_items:
            return raw_items, None

        # handle_items_to_parse only warns when the expression is not a list.
        parsed_items = await jq_processor._search(dict(file), items_to_parse)
        if isinstance(parsed_items, list):
            return [], None
        return [], (
            f"itemsToParse expression '{items_to_parse}' must return a list, "
            f"got {type(parsed_items).__name__}"
        )

    async def _validate_items(
        self,
        raw_items: List[Dict[str, Any]],
        resource_config: GithubFileResourceConfig,
    ) -> List[ValidationResult]:
        async def validate_item(raw_item: Dict[str, Any]) -> ValidationResult:
            async with self._validation_semaphore:
                return await self._validate_entity_against_port(
                    cast(FileObject, raw_item), resource_config
                )

        return list(
            await asyncio.gather(*(validate_item(raw_item) for raw_item in raw_items))
        )

    async def _validate_file_against_port(
        self, file: FileObject, resource_config: GithubFileResourceConfig
    ) -> ValidationResult:
        """Validate the entities sync would create: expand itemsToParse, then apply the selector query."""
        jq_processor = JQEntityProcessor(ocean)
        items_to_parse = resource_config.port.items_to_parse
        if not items_to_parse:
            if not await jq_processor._search_as_bool(
                dict(file), resource_config.selector.query
            ):
                return {"success": True, "errors": [], "response": None}
            return await self._validate_entity_against_port(file, resource_config)

        raw_items, error = await self._expand_items(
            file, resource_config, items_to_parse, jq_processor
        )
        if error:
            return {"success": False, "errors": [error], "response": None}

        selected_items = [
            (index, raw_item)
            for index, raw_item in enumerate(raw_items)
            if await jq_processor._search_as_bool(
                raw_item, resource_config.selector.query
            )
        ]
        results = await self._validate_items(
            [raw_item for _, raw_item in selected_items], resource_config
        )
        errors = [
            f"{items_to_parse}[{index}]: {error}"
            for (index, _), result in zip(selected_items, results)
            for error in result["errors"]
        ]
        if len(errors) > MAX_REPORTED_ITEM_ERRORS:
            hidden_count = len(errors) - MAX_REPORTED_ITEM_ERRORS
            errors = errors[:MAX_REPORTED_ITEM_ERRORS] + [
                f"... and {hidden_count} more item errors"
            ]
        return {
            "success": not errors,
            "errors": errors,
            "response": [result["response"] for result in results],
        }

    async def _validate_entity_against_port(
        self, entity: FileObject, resource_config: GithubFileResourceConfig
    ) -> ValidationResult:
        """Validate an entity against Port's API using upsert_entity with validation_only=True."""
        identifier: Any = "unknown"
        try:
            jq_processor = JQEntityProcessor(ocean)

            entity_mappings = {
                "identifier": resource_config.port.entity.mappings.identifier,
                "title": resource_config.port.entity.mappings.title,
                "blueprint": resource_config.port.entity.mappings.blueprint,
                "properties": resource_config.port.entity.mappings.properties,
                "relations": resource_config.port.entity.mappings.relations,
            }

            extracted_values = await jq_processor._search_as_object(
                dict(entity), entity_mappings
            )

            blueprint = extracted_values["blueprint"]
            properties = extracted_values["properties"]
            relations = extracted_values["relations"]
            identifier = extracted_values["identifier"]
            title = extracted_values["title"]

            if not isinstance(blueprint, str):
                return {
                    "success": False,
                    "errors": ["Blueprint is not a string"],
                    "response": None,
                }

            if not isinstance(properties, dict):
                return {
                    "success": False,
                    "errors": ["Properties is not a dictionary"],
                    "response": None,
                }

            if not isinstance(relations, dict):
                return {
                    "success": False,
                    "errors": ["Relations is not a dictionary"],
                    "response": None,
                }

            entity_obj = Entity(
                identifier=identifier,
                blueprint=blueprint,
                title=title,
                properties=properties,
                relations=relations,
            )

            request_options = RequestOptions(
                validation_only=True,
                merge=True,
                create_missing_related_entities=False,
                delete_dependent_entities=False,
            )

            # 404 not_found still returns False without raising.
            validation_response = await ocean.port_client.upsert_entity(
                entity=entity_obj,
                request_options=request_options,
                should_raise=True,
            )

            if validation_response is False:
                error_message = (
                    f"Port validation failed for entity '{identifier}': "
                    "resource not found"
                )
                logger.error(error_message)
                return {
                    "success": False,
                    "errors": [error_message],
                    "response": None,
                }

            return {"success": True, "errors": [], "response": validation_response}

        except httpx.HTTPStatusError as e:
            error_message = _format_port_http_error(e)
            return {"success": False, "errors": [error_message], "response": None}
        except Exception as e:
            logger.error(f"Failed to validate entity {identifier}: {str(e)}")
            return {"success": False, "errors": [str(e)], "response": None}


def get_file_validation_mappings(
    port_app_config: GithubPortAppConfig,
) -> List[ResourceConfigToPatternMapping]:
    """
    Get file resource configurations with validation enabled for the specific repository.

    Returns:
        List of file resource configurations that have validation enabled for the specific repository
    """

    matching_mappings = []
    for resource in port_app_config.resources:
        # Check if this is a file resource by checking the kind attribute
        if hasattr(resource, "kind") and resource.kind == "file":
            file_resource_config = cast("GithubFileResourceConfig", resource)
            selector = file_resource_config.selector

            matching_patterns = [
                pattern for pattern in selector.files if pattern.validation_check
            ]

            if matching_patterns:
                matching_mappings.append(
                    ResourceConfigToPatternMapping(
                        resource_config=file_resource_config, patterns=matching_patterns
                    )
                )

    return matching_mappings
