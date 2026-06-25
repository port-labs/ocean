from typing import Any

import httpx
from loguru import logger
from pydantic import BaseModel

from github.actions.abstract_github_executor import AbstractGithubExecutor
from github.helpers.exceptions import InvalidActionParametersException
from port_ocean.context.ocean import ocean
from port_ocean.core.models import ActionRun, WorkflowNodeRun


class ExternalProperty(BaseModel):
    property_name: str
    value: str | None


def _extract_changed_properties(
    diff: dict[str, Any],
) -> dict[str, Any]:
    """
    Given a Port audit-log diff dict:
        { "before": {"properties": {...}}, "after": {"properties": {...}} }

    Returns a flat dict of only the properties whose value changed
    (present in `after` and different from `before`).

    New properties (not in `before`) are included.
    Deleted properties (not in `after`) are skipped — GitHub requires
    an explicit null / empty-string value; callers can handle that separately.
    """
    before: dict[str, Any] = (diff.get("before") or {}).get("properties") or {}
    after: dict[str, Any] = (diff.get("after") or {}).get("properties") or {}

    changed: dict[str, Any] = {}
    for key, new_val in after.items():
        if before.get(key) != new_val:
            changed[key] = new_val

    # Properties removed from `after` entirely are unset in GitHub by sending null.
    for key in before:
        if key not in after:
            changed[key] = None

    return changed


def _filter_by_property_names(
    changed: dict[str, Any],
    property_names: list[str] | None,
) -> dict[str, Any]:
    if not property_names:
        return changed
    allowed = set(property_names)
    return {name: value for name, value in changed.items() if name in allowed}


def _build_github_properties_payload(
    changed: dict[str, Any],
) -> list[ExternalProperty]:
    """
    Convert a flat {name: value} dict into the GitHub properties array:
        [ExternalProperty(property_name="...", value="...")]
    """
    return [
        ExternalProperty(
            property_name=name, value=None if value is None else str(value)
        )
        for name, value in changed.items()
    ]


def _parse_property_sync_config(
    config: Any,
) -> tuple[dict[str, Any], list[str] | None]:
    if not isinstance(config, dict):
        raise InvalidActionParametersException(
            "'propertySync' must be an object with 'diff' and optional 'propertyNames'"
        )

    diff = config.get("diff")
    if not isinstance(diff, dict):
        raise InvalidActionParametersException(
            "'propertySync.diff' must be a Port audit log diff object"
        )

    property_names = config.get("propertyNames")
    if property_names is None:
        return diff, None
    if not isinstance(property_names, list) or not all(
        isinstance(name, str) for name in property_names
    ):
        raise InvalidActionParametersException(
            "'propertySync.propertyNames' must be a list of property identifiers"
        )

    return diff, property_names


class UpdateRepoExternalPropertiesExecutor(AbstractGithubExecutor):
    """
    Writes changed Port entity properties back to GitHub as repository
    external / custom properties.
    """

    ACTION_NAME = "update_repo_external_properties"
    WEBHOOK_PROCESSOR_CLASS = None

    async def execute(self, run: ActionRun | WorkflowNodeRun) -> None:
        props = run.execution_properties

        org: str | None = props.get("org")
        repo: str | None = props.get("repo")
        property_sync: Any = props.get("propertySync")

        if not org or not repo or not property_sync:
            raise InvalidActionParametersException(
                "'org', 'repo', and 'propertySync' are required execution properties"
            )

        diff, property_names = _parse_property_sync_config(property_sync)

        with logger.contextualize(org=org, repo=repo):
            logger.info("Processing external property update")

            changed = _filter_by_property_names(
                _extract_changed_properties(diff), property_names
            )

            if not changed:
                logger.info(
                    "No properties changes detected — nothing to push to GitHub"
                )
                await ocean.port_client.report_run_completed(
                    run, success=True, message="No changes to apply."
                )
                return

            github_properties = _build_github_properties_payload(changed)

            changed_properties = [p.property_name for p in github_properties]
            logger.info(
                f"Pushing {len(github_properties)} external properties to GitHub",
                changed_properties=changed_properties,
            )

            await ocean.port_client.post_run_log(
                run,
                f"Updating {len(github_properties)} external properties on {org}/{repo}: "
                + ", ".join(changed_properties),
            )

            try:
                body = {
                    "repository_names": [repo],
                    "properties": [p.dict() for p in github_properties],
                }
                await self.rest_client.make_request(
                    f"{self.rest_client.base_url}/orgs/{org}/properties/external/values",
                    method="PATCH",
                    json_data=body,
                    ignore_default_errors=False,
                )
            except Exception as e:
                error_message = str(e)
                if isinstance(e, httpx.HTTPStatusError):
                    error_message = e.response.json().get("message", str(e))
                    logger.error(
                        "GitHub API error while updating external properties",
                        status_code=e.response.status_code,
                        message=error_message,
                    )
                raise Exception(f"Error updating external properties: {error_message}")

            logger.info("Successfully updated external properties")
            await ocean.port_client.report_run_completed(
                run,
                success=True,
                message=f"Updated {len(github_properties)} external properties on {org}/{repo}.",
            )
