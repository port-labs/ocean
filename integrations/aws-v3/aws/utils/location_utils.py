from typing import cast

from aws import Consts
from port_ocean.context.ocean import ocean


class LocationUtils:
    _partition: str = ''

    @classmethod
    def get_partition(cls) -> str:
        if not cls._partition:
            if ocean.integration_config.get('aws_partition'):
                cls._partition = cast(str, ocean.integration_config.get('aws_partition'))
            elif ocean.integration_config.get('accountRoleArn'):
                cls._partition = cast(str, ocean.integration_config.get('accountRoleArn')).split(':')[1]
            else:
                cls._partition = Consts.default_partition

        return cls._partition
