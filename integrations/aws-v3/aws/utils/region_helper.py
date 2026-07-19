from typing import cast

from aiobotocore.session import AioSession

from aws.utils.consts import Consts
from port_ocean.context.ocean import ocean


class RegionHelper:
    _partition: str = ""
    _available_regions: list[str] = []

    @classmethod
    def get_partition(cls) -> str:
        if not cls._partition:
            if partition := ocean.integration_config.get("aws_partition"):
                cls._partition = cast(str, partition)
            elif account_role_arn := ocean.integration_config.get("account_role_arn"):
                cls._partition = cast(str, account_role_arn).split(":")[1]
            elif account_role_arns := ocean.integration_config.get("account_role_arns"):
                cls._partition = str(account_role_arns[0]).split(":")[1]
            else:
                cls._partition = Consts.default_partition

        return cls._partition

    @classmethod
    async def get_all_available_regions(cls, session: AioSession) -> list[str]:
        if not cls._available_regions:
            cls._available_regions = await session.get_available_regions(
                "ec2", partition_name=cls.get_partition()
            )

        return cls._available_regions

    @classmethod
    async def get_first_available_region(cls, session: AioSession) -> str | None:
        regions = await cls.get_all_available_regions(session)
        return regions[0] if regions else None

    @classmethod
    async def get_custom_partition_region_or_none(
        cls, session: AioSession
    ) -> str | None:
        return (
            None
            if cls.get_partition() == Consts.default_partition
            else await cls.get_first_available_region(session)
        )
