from typing import cast

from aiobotocore.session import AioSession

from aws import Consts
from port_ocean.context.ocean import ocean


class LocationUtils:
    _partition: str = ''
    _available_regions: list[str] = []

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

    @classmethod
    async def get_all_available_regions(cls, session: AioSession) -> list[str]:
        if not cls._available_regions:
            cls._available_regions = await session.get_available_regions('ec2', partition_name=cls.get_partition())

        return cls._available_regions

    @classmethod
    async def get_first_available_region(cls, session: AioSession) -> str | None:
        regions = await cls.get_all_available_regions(session)
        return regions[0] if regions else None
