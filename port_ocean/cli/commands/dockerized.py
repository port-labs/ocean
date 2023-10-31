import os
import subprocess
from typing import List, Dict
from port_ocean.cli.commands.main import console

from port_ocean.config.settings import ApplicationSettings
from port_ocean.logger_setup import setup_logger


def generate_list_of_environments_for_docker_cli(
    environments: Dict[str, str]
) -> List[str]:
    return [f"-e {key}='{value}'" for key, value in environments.items()]


def run_once(integration: str, version: str) -> None:
    application_settings = ApplicationSettings()
    setup_logger(application_settings.log_level)

    environments = os.environ.copy()
    filtered_environments = {
        key: value
        for key, value in environments.items()
        if key.startswith("PORT__")
        or key.startswith("OCEAN__")
        or key.startswith("APPLICATION__")
    }
    docker_cli_environments = generate_list_of_environments_for_docker_cli(
        filtered_environments
    )

    image_name = f"ghcr.io/port-labs/port-ocean-{integration}:{version}"

    docker_run_command = f"docker run -it --platform=linux/amd64 {' '.join(docker_cli_environments)} {image_name}"

    console.print(f"Running: {docker_run_command}")

    subprocess.run(docker_run_command, shell=True)

    console.print(f"Finished running: {docker_run_command}")

    return
