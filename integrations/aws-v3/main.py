from port_ocean.context.ocean import ocean
from integration import AWSResourceConfig
import asyncio
from port_ocean.context.event import event
from aws.auth.session_factory import get_all_account_sessions
from aws.core import (
    resync_resources_for_account_with_session,
    ASYNC_GENERATOR_RESYNC_TYPE,
)
from port_ocean.utils.async_iterators import (
    semaphore_async_iterator,
    stream_async_iterators_tasks,
)
import functools
import typing

ACCOUNT_CONCURRENCY_LIMIT = 10


@ocean.on_start()
async def on_start() -> None:
    print("Starting aws-v3 integration")


@ocean.on_resync()
async def resync_all(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    aws_resource_config = typing.cast(AWSResourceConfig, event.resource_config)
    account_semaphore = asyncio.Semaphore(ACCOUNT_CONCURRENCY_LIMIT)
    account_tasks = []

    async for account, session in get_all_account_sessions():
        account_tasks.append(
            semaphore_async_iterator(
                account_semaphore,
                functools.partial(
                    resync_resources_for_account_with_session,
                    account,
                    session,
                    kind,
                    aws_resource_config,
                ),
            )
        )
    async for batch in stream_async_iterators_tasks(*account_tasks):
        yield batch
