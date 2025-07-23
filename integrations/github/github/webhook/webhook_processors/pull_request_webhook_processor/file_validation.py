from dataclasses import dataclass
from typing import Any, Dict, List, Optional, TypedDict, cast
from loguru import logger
from github.core.exporters.file_exporter.utils import (
    FileObject,
)
from integration import GithubFileResourceConfig, GithubFilePattern, GithubPortAppConfig
from github.core.exporters.pull_request_exporter import (
    RestPullRequestExporter,
)
from port_ocean.clients.port.types import RequestOptions
from port_ocean.context.ocean import ocean
from port_ocean.core.models import Entity
from port_ocean.core.handlers.entity_processor import JQEntityProcessor


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


class FileValidationService:
    """Service for validating files during pull request processing."""

    def __init__(self, pr_exporter: RestPullRequestExporter) -> None:
        self.pr_exporter = pr_exporter

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
            f"Starting validation for file {file_path} in PR {repo_name}/{pr_number}"
        )

        validation_check_status = "completed"
        validation_check_conclusion = "success"
        validation_check_title = "File validation passed"
        validation_check_summary = "Successfully validated file"
        validation_check_details = "All files passed validation"

        try:
            check_run_id = await self.pr_exporter.create_validation_check(
                repo_name=repo_name, head_sha=head_sha
            )
        except Exception as e:
            logger.error(f"Failed to create validation check: {str(e)}")
            return

        try:
            validation_errors = []
            result: ValidationResult = await self._validate_entity_against_port(
                changed_file, resource_config
            )

            logger.info(
                f"Validation result {'success' if result['success'] else 'failure'} for file {file_path}"
            )

            if not result["success"]:
                error_msg = (
                    f"Validation failed for {file_path}: {', '.join(result['errors'])}"
                )
                validation_errors.append(error_msg)

            if validation_errors:
                validation_check_conclusion = "failure"
                validation_check_title = "File validation failed"
                validation_check_summary = (
                    f"Found {len(validation_errors)} validation errors"
                )
                validation_check_details = "\n".join(validation_errors)

        except Exception as e:
            logger.error(f"Validation error: {str(e)}")
            validation_check_conclusion = "failure"
            validation_check_title = "File validation error"
            validation_check_summary = "An error occurred during validation"
            validation_check_details = str(e)

        await self.pr_exporter.update_check_run(
            repo_name,
            check_run_id,
            validation_check_status,
            validation_check_conclusion,
            validation_check_title,
            validation_check_summary,
            validation_check_details,
        )

    async def _validate_entity_against_port(
        self, entity: FileObject, resource_config: GithubFileResourceConfig
    ) -> ValidationResult:
        """Validate an entity against Port's API using upsert_entity with validation_only=True."""
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

            validation_response = await ocean.port_client.upsert_entity(
                entity=entity_obj,
                request_options=request_options,
                should_raise=False,
            )

            return {"success": True, "errors": [], "response": validation_response}

        except Exception as e:
            logger.error(f"Failed to validate entity {identifier}: {str(e)}")
            return {"success": False, "errors": [str(e)], "response": None}


def get_file_validation_mappings(
    port_app_config: GithubPortAppConfig, repo_name: str
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

            matching_patterns = []
            for pattern in selector.files:
                if pattern.validation_check and any(
                    repo.name == repo_name for repo in pattern.repos
                ):
                    matching_patterns.append(pattern)

            if matching_patterns:
                matching_mappings.append(
                    ResourceConfigToPatternMapping(
                        resource_config=file_resource_config, patterns=matching_patterns
                    )
                )

    return matching_mappings
