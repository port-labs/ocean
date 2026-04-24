from typing import Any, Dict

import yaml
from loguru import logger

from github.clients.client_factory import create_github_client
from github.core.exporters.file_exporter.core import RestFileExporter
from github.core.options import FileContentOptions
from port_ocean.exceptions.api import EmptyPortAppConfigError

ORG_CONFIG_REPO = ".github-private"
ORG_CONFIG_FILE = "port-app-config.yml"


def is_repo_managed_mapping(integration: Dict[str, Any]) -> bool:
    """Check if the mapping is managed by the repository."""
    config = integration.get("config") or {}
    return bool(config.get("repoManagedMapping"))


async def load_org_port_app_config(github_org: str) -> Dict[str, Any]:
    """
    Load the global Port app config from the GitHub organization config repository.

    Get the file `<github_org>/.github-private/port-app-config.yml` from the repository's default
    branch and using it as the single global mapping.
    """

    rest_client = create_github_client()
    repo_metadata = await rest_client.send_api_request(
        f"{rest_client.base_url}/repos/{github_org}/{ORG_CONFIG_REPO}"
    )
    if not repo_metadata:
        logger.error(
            "Organization config repository '.github-private' was not found "
            f"for organization {github_org}"
        )
        raise EmptyPortAppConfigError()

    default_branch = repo_metadata["default_branch"]
    exporter = RestFileExporter(rest_client)
    file_response = await exporter.get_resource(
        FileContentOptions(
            organization=github_org,
            repo_name=ORG_CONFIG_REPO,
            file_path=ORG_CONFIG_FILE,
            branch=default_branch,
        )
    )

    if not file_response:
        logger.error(
            f"Port app config file not found using GitHub Global configuration for {github_org}",
            extra={
                "github_org": github_org,
                "org_config_repo": ORG_CONFIG_REPO,
                "default_branch": default_branch,
                "file_path": ORG_CONFIG_FILE,
            },
        )
        raise EmptyPortAppConfigError()

    content = file_response.get("content")
    if not content:
        logger.error(
            f"Port app config file not found or empty using GitHub Global configuration for {github_org}",
            extra={
                "github_org": github_org,
                "org_config_repo": ORG_CONFIG_REPO,
                "default_branch": default_branch,
                "file_path": ORG_CONFIG_FILE,
            },
        )
        raise EmptyPortAppConfigError()

    try:
        file_config = yaml.safe_load(content)
    except Exception as exc:
        logger.exception(
            "Failed to parse GitHub Port app config YAML from file "
            f"port-app-config.yml: {exc}"
        )
        raise EmptyPortAppConfigError("Port app config is invalid") from exc

    if file_config is None:
        logger.error(
            "Parsed GitHub Port app config from organization config "
            "repository is empty"
        )
        raise EmptyPortAppConfigError("Config is empty")

    if not isinstance(file_config, dict):
        log_message = f"Expected YAML mapping (dict), got {type(file_config).__name__}"
        logger.error(log_message)
        raise EmptyPortAppConfigError(log_message)

    logger.info(
        f"Successfully loaded Port app config from GitHub organization {github_org}",
        extra={
            "github_org": github_org,
            "org_config_repo": ORG_CONFIG_REPO,
            "default_branch": default_branch,
            "file_path": ORG_CONFIG_FILE,
        },
    )
    return file_config
