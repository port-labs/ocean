from typing import cast

from aws import Consts
from port_ocean.context.ocean import ocean

def get_partition() -> str:
    if ocean.integration_config.get('aws_partition'):
        return cast(str, ocean.integration_config.get('aws_partition'))

    if ocean.integration_config.get('accountRoleArn'):
        return cast(str, ocean.integration_config.get('accountRoleArn')).split(':')[1]

    return Consts.default_partition
