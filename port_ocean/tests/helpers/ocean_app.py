import sys
from inspect import getmembers
from pathlib import Path
from typing import List, Tuple

from yaml import safe_load

from port_ocean.bootstrap import create_default_app
from port_ocean.core.handlers.port_app_config.models import ResourceConfig
from port_ocean.core.ocean_types import RESYNC_RESULT
from port_ocean.ocean import Ocean
from port_ocean.utils.misc import get_spec_file, load_module


def get_integration_ocean_app(integration_path: str) -> Ocean:
    spec_file = get_spec_file(Path(integration_path))

    config_factory = None if not spec_file else spec_file.get("configurations", [])

    default_app = create_default_app(
        integration_path,
        config_factory,
        {
            "port": {
                "client_id": "bla",
                "client_secret": "bla",
            },
        },
    )
    main_path = f"{integration_path}/main.py"
    sys.path.append(integration_path)
    app_module = load_module(main_path)
    app: Ocean = {name: item for name, item in getmembers(app_module)}.get(
        "app", default_app
    )

    return app


def get_integation_resource_configs(integration_path: str) -> List[ResourceConfig]:
    with open(
        f"{integration_path}/.port/resources/port-app-config.yml"
    ) as port_app_config_file:
        resource_configs = safe_load(port_app_config_file)

    return [ResourceConfig(**item) for item in resource_configs["resources"]]


async def get_raw_result_on_integration_sync_resource_config(
    app: Ocean, resource_config: ResourceConfig
) -> Tuple[RESYNC_RESULT, List[Exception]]:
    resource_result = await app.integration._get_resource_raw_results(resource_config)

    return resource_result
