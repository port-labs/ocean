import sys
from inspect import getmembers
from typing import List, Union

from yaml import safe_load

from port_ocean.bootstrap import create_default_app
from port_ocean.core.handlers.port_app_config.models import ResourceConfig
from port_ocean.ocean import Ocean
from port_ocean.utils.misc import load_module


def get_integration_app(integration_path: str) -> Ocean:
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
