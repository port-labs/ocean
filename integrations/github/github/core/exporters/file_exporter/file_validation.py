from typing import Dict, List, Any
from loguru import logger
from github.core.exporters.file_exporter.core import RestFileExporter
from github.core.exporters.file_exporter.utils import get_matching_files, parse_content
from github.core.options import FileContentOptions
from integration import GithubFilePattern
from ocean.integrations.github.github.core.exporters.pull_request_exporter import (
    RestPullRequestExporter,
)
from port_ocean.context.ocean import ocean


async def find_matching_files_for_validation(
    changed_files: List[Dict[str, Any]], validation_mappings: List[GithubFilePattern]
) -> List[Dict[str, Any]]:
    """Find files that match validation patterns."""

    matching_files = get_matching_files(changed_files, validation_mappings)

    return [
        {
            "filename": file_info["filename"],
            "pattern": file_info["patterns"][0],
            "status": file_info.get("status", "unknown"),
        }
        for file_info in matching_files
    ]


async def create_port_entities_for_validation(
    parsed_content: Any, mapping: GithubFilePattern, repo_name: str
) -> List[Dict[str, Any]]:
    """Create Port entities from parsed content for validation."""
    try:
        if isinstance(parsed_content, dict):
            # Single entity
            entity = {
                "identifier": parsed_content.get(
                    "identifier", f"{repo_name}-{mapping.path}"
                ),
                "title": parsed_content.get("title", f"Entity from {mapping.path}"),
                "blueprint": parsed_content.get("blueprint", "default"),
                "properties": parsed_content.get("properties", {}),
                "relations": parsed_content.get("relations", {}),
            }
            return [entity]

        elif isinstance(parsed_content, list):
            # Multiple entities
            entities = []
            for item in parsed_content:
                if isinstance(item, dict):
                    entity = {
                        "identifier": item.get(
                            "identifier", f"{repo_name}-{mapping.path}-{len(entities)}"
                        ),
                        "title": item.get("title", f"Entity from {mapping.path}"),
                        "blueprint": item.get("blueprint", "default"),
                        "properties": item.get("properties", {}),
                        "relations": item.get("relations", {}),
                    }
                    entities.append(entity)
            return entities

        else:
            logger.warning(
                f"Unexpected content type for {mapping.path}: {type(parsed_content)}"
            )
            return []

    except Exception as e:
        logger.error(f"Failed to create Port entities for {mapping.path}: {str(e)}")
        return []


async def validate_entity_against_port(
    entity: Dict[str, Any], blueprint_identifier: str
) -> Dict[str, Any]:
    """Validate an entity against Port's API."""
    try:
        # Use Port's validation endpoint with validation_only: true
        validation_response = await ocean.port_client.validate_entity(
            entity_data=entity,
            blueprint_identifier=blueprint_identifier,
            validation_only=True,
        )

        return {"success": True, "errors": [], "response": validation_response}

    except Exception as e:
        logger.error(
            f"Failed to validate entity {entity.get('identifier', 'unknown')}: {str(e)}"
        )
        return {"success": False, "errors": [str(e)], "response": None}


class FileValidationService:
    """Service for validating files during pull request processing."""

    def __init__(
        self, file_exporter: RestFileExporter, pr_exporter: RestPullRequestExporter
    ) -> None:
        self.file_exporter = file_exporter
        self.pr_exporter = pr_exporter

    async def validate_pull_request_files(
        self,
        validation_mappings: List[GithubFilePattern],
        changed_files: List[Dict[str, Any]],
        repo_name: str,
        head_sha: str,
        head_ref: str,
        pr_number: int,
    ) -> None:
        """Validate files in a pull request against Port configuration."""

        logger.info(f"Starting validation for PR {repo_name}/{pr_number}")

        matching_files = await find_matching_files_for_validation(
            changed_files, validation_mappings
        )
        if not matching_files:
            return

        logger.info(f"Found {len(matching_files)} files to validate")

        check_run_id = await self.pr_exporter.create_validation_check(
            repo_name=repo_name, head_sha=head_sha
        )

        validation_check_status = "completed"
        validation_check_conclusion = "success"
        validation_check_title = "File validation passed"
        validation_check_summary = f"Successfully validated {len(matching_files)} files"
        validation_check_details = "All files passed validation"

        try:
            validation_errors = await self._validate_files_against_port_blueprints(
                matching_files, repo_name, head_ref
            )

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

    async def _validate_files_against_port_blueprints(
        self, matching_files: List[Dict[str, Any]], repo_name: str, branch: str
    ) -> List[str]:
        """Validate all matching files."""
        validation_errors = []

        for file_info in matching_files:
            file_path = file_info["filename"]
            pattern = file_info["pattern"]

            try:
                file_content_response = await self.file_exporter.get_resource(
                    FileContentOptions(
                        repo_name=repo_name, file_path=file_path, branch=branch
                    )
                )
                decoded_content = file_content_response.get("content")
                if not decoded_content:
                    logger.warning(f"File {file_path} has no content")
                    validation_errors.append(
                        f"Could not retrieve content for {file_path}"
                    )
                    continue

                parsed_content = parse_content(decoded_content, file_path)

                entities = await create_port_entities_for_validation(
                    parsed_content, pattern, repo_name
                )
                if not entities:
                    validation_errors.append(f"No valid entities found in {file_path}")
                    continue

                for entity in entities:
                    blueprint_id = entity.get("blueprint", "default")
                    result = await validate_entity_against_port(entity, blueprint_id)

                    if not result["success"]:
                        error_msg = f"Validation failed for {entity.get('identifier')} in {file_path}: {', '.join(result['errors'])}"
                        validation_errors.append(error_msg)

            except Exception as e:
                validation_errors.append(f"Error validating {file_path}: {str(e)}")

        return validation_errors
