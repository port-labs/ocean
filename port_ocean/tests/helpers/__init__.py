import sys
from inspect import getmembers
from typing import Dict, List, Set, Tuple, Union

from yaml import safe_load

from port_ocean.bootstrap import create_default_app
from port_ocean.core.handlers.port_app_config.models import ResourceConfig
from port_ocean.core.ocean_types import RESYNC_RESULT
from port_ocean.ocean import Ocean
from port_ocean.utils.misc import load_module


def get_integration_ocean_app(integration_path: str) -> Ocean:
    default_app = create_default_app(
        integration_path,
        None,
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


def get_integation_resource_config_by_name(
    integration_path: str, kind: str
) -> Union[ResourceConfig, None]:
    resource_configs = get_integation_resource_configs(integration_path)

    relevant_configs = [x for x in resource_configs if x.kind == kind]

    return relevant_configs[0] if len(relevant_configs) else None


async def get_raw_result_on_integration_sync_kinds(
    integration_path: str, override_kinds: Union[Set[str], None] = None
) -> Dict[str, List[Tuple[RESYNC_RESULT, List[Exception]]]]:
    app = get_integration_ocean_app(integration_path)

    resource_configs = get_integation_resource_configs(integration_path)

    if override_kinds:
        resource_configs = [x for x in resource_configs if x.kind in override_kinds]

    results: Dict[str, List[Tuple[RESYNC_RESULT, List[Exception]]]] = {}

    for resource_config in resource_configs:
        resource_result = await app.integration._get_resource_raw_results(
            resource_config
        )

        results[resource_config.kind] = results.get(resource_config.kind, []) + [
            resource_result
        ]

    return results
