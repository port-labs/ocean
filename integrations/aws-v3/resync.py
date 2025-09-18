import asyncio
from functools import partial
from typing import Any, Callable, List, Type, AsyncIterator, cast, TYPE_CHECKING

from loguru import logger
from port_ocean.context.event import event
from port_ocean.core.ocean_types import ASYNC_GENERATOR_RESYNC_TYPE
from port_ocean.utils.async_iterators import (
    semaphore_async_iterator,
    stream_async_iterators_tasks,
)

from integration import AWSResourceConfig
from aws.auth.session_factory import get_all_account_sessions
from aws.core.helpers.utils import get_allowed_regions, is_access_denied_exception
from aws.core.modeling.resource_models import ResourceRequestModel
from aws.auth.session_factory import AccountInfo
from aiobotocore.session import AioSession
from abc import ABC, abstractmethod

if TYPE_CHECKING:
    from aws.core.interfaces.exporter import IResourceExporter

_MAX_CONCURRENT_REGIONS = 10
_MAX_CONCURRENT_ACCOUNTS = 10


async def safe_iterate(
    ait: AsyncIterator[Any], identifier: str, kind: str
) -> ASYNC_GENERATOR_RESYNC_TYPE:
    """Safely iterates over an async iterator, handling access denied exceptions."""
    try:
        async for item in ait:
            yield item
    except Exception as e:
        if is_access_denied_exception(e):
            logger.debug(
                f"{identifier} failed during resync of {kind}: {e}, skipping ..."
            )
            return
        raise


class ResyncStrategy(ABC):
    """Abstract base for resync strategies (regional or global)."""

    def __init__(
        self,
        exporter: "IResourceExporter",
        options_factory: Callable[[str], Any],
        kind: str,
        account_id: str | None = None,
    ):
        self.exporter = exporter
        self.options_factory = options_factory
        self.kind = kind
        self.account_id = account_id

    @abstractmethod
    def run(self, regions: List[str]) -> ASYNC_GENERATOR_RESYNC_TYPE:
        pass


class RegionalResyncStrategy(ResyncStrategy):
    """Strategy for regional resource resync across multiple regions concurrently."""

    def __init__(
        self,
        exporter: "IResourceExporter",
        options_factory: Callable[[str], Any],
        kind: str,
        account_id: str,
        max_concurrent: int = _MAX_CONCURRENT_REGIONS,
    ):
        super().__init__(exporter, options_factory, kind, account_id)
        self.max_concurrent = max_concurrent

    async def run(self, regions: List[str]) -> ASYNC_GENERATOR_RESYNC_TYPE:

        logger.info(
            f"Processing {self.kind} across {len(regions)} regions for account {self.account_id}"
        )
        semaphore = asyncio.Semaphore(self.max_concurrent)

        tasks = [
            safe_iterate(
                semaphore_async_iterator(
                    semaphore,
                    partial(
                        self.exporter.get_paginated_resources,
                        self.options_factory(region),
                    ),
                ),
                region,
                self.kind,
            )
            for region in regions
        ]

        async for batch in stream_async_iterators_tasks(*tasks):
            if batch:
                yield batch


class GlobalResyncStrategy(ResyncStrategy):
    """Strategy for global resource resync (attempts regions until success)."""

    async def run(self, regions: List[str]) -> ASYNC_GENERATOR_RESYNC_TYPE:
        for region in regions:
            try:
                options = self.options_factory(region)
                async for batch in self.exporter.get_paginated_resources(options):
                    yield batch
                return  # Success in one region → stop
            except Exception as e:
                if is_access_denied_exception(e):
                    logger.debug(
                        f"Failed to fetch global resource {self.kind} for account {self.account_id} in region {region}: {e}. Skipping this region ..."
                    )
                    continue
                raise
        logger.error(
            f"All candidate regions [{regions}] failed for global resource resync of {self.kind}"
        )


class ResyncAWSService:
    """Facade service to resync resources across accounts using a strategy."""

    def __init__(
        self,
        kind: str,
        exporter_cls: Type["IResourceExporter"],
        request_cls: Type[ResourceRequestModel],
        regional: bool,
    ):
        self.kind = kind
        self.exporter_cls = exporter_cls
        self.request_cls = request_cls
        self.regional = regional

        self.aws_resource_config = cast(AWSResourceConfig, event.resource_config)
        self.include_actions = self.aws_resource_config.selector.include_actions
        self.max_concurrent_accounts = (
            self.aws_resource_config.selector.max_concurrent_accounts
            or _MAX_CONCURRENT_ACCOUNTS
        )

    def _create_options_factory(self, account_id: str) -> Callable[[str], Any]:
        def options_factory(region: str) -> Any:
            return self.request_cls(
                region=region,
                include=self.include_actions,
                account_id=account_id,
            )

        return options_factory

    async def _account_resync_generator(
        self, account: AccountInfo, session: AioSession, regions: List[str]
    ) -> AsyncIterator[List[dict[Any, Any]]]:
        logger.info(
            f"Resyncing {self.kind} for account {account['Id']} across {len(regions)} regions"
        )
        exporter = self.exporter_cls(session)
        options_factory = self._create_options_factory(account["Id"])

        strategy: ResyncStrategy
        if self.regional:
            strategy = RegionalResyncStrategy(
                exporter,
                options_factory,
                self.kind,
                account_id=account["Id"],
            )
        else:
            strategy = GlobalResyncStrategy(
                exporter,
                options_factory,
                self.kind,
            )

        async for batch in strategy.run(regions):
            yield batch

    async def __aiter__(self) -> ASYNC_GENERATOR_RESYNC_TYPE:
        semaphore = asyncio.Semaphore(self.max_concurrent_accounts)
        tasks: List[AsyncIterator[List[dict[Any, Any]]]] = []

        async for account, session in get_all_account_sessions():
            regions = await get_allowed_regions(
                session, self.aws_resource_config.selector
            )
            tasks.append(
                safe_iterate(
                    semaphore_async_iterator(
                        semaphore,
                        partial(
                            self._account_resync_generator, account, session, regions
                        ),
                    ),
                    account["Id"],
                    self.kind,
                )
            )

        async for batch in stream_async_iterators_tasks(*tasks):
            if batch:
                yield batch
