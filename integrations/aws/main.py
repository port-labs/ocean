import json
import typing

from fastapi import Response, status
import fastapi
from starlette import responses
from pydantic import BaseModel
import asyncio

from port_ocean.core.models import Entity

from utils.resources import (
    is_global_resource,
    resync_custom_kind,
    describe_single_resource,
    fix_unserializable_date_properties,
    resync_cloudcontrol,
    resync_sqs_queue,
    resync_resource_group,
)

from utils.aws import (
    get_accounts,
    get_sessions,
    validate_request,
    get_arn_for_account_id,
    initialize_aws_credentials,
)
from port_ocean.context.ocean import ocean
from loguru import logger
from port_ocean.core.ocean_types import ASYNC_GENERATOR_RESYNC_TYPE
from port_ocean.context.event import event
from utils.overrides import AWSPortAppConfig, AWSResourceConfig
from utils.misc import (
    get_matching_kinds_and_blueprints_from_config,
    CustomProperties,
    ResourceKindsWithSpecialHandling,
    is_access_denied_exception,
    is_server_error,
)
from port_ocean.utils.async_iterators import (
    semaphore_async_iterator,
    stream_async_iterators_tasks,
)
import functools
from aiobotocore.session import AioSession
from aws.core.exporters.sqs_exporter import SQSExporter
from aws.core.exporters.resource_group_exporter import ResourceGroupExporter
from aws.core.options import ListSQSOptions


async def get_regions(): ...


@ocean.on_resync(kind=ResourceKindsWithSpecialHandling.SQS_QUEUE)
async def resync_sqs(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    aws_resource_config = typing.cast(AWSResourceConfig, event.resource_config)
    selector = aws_resource_config.selector
    region_semaphore = asyncio.Semaphore(5)
    async for session, region in get_sessions(selector, None):
        async for batch in semaphore_async_iterator(
            region_semaphore,
            functools.partial(
                resync_sqs_queue,
                kind,
                session,
                region,
                aws_resource_config,
            ),
        ):
            yield batch


@ocean.on_resync(kind=ResourceKindsWithSpecialHandling.SQS_QUEUE)
async def resync_sqs(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    for account_session in get_accounts():
        async for region in get_regions(account_session["Arn"]):
            async with SQSExporter(account_session, region) as exporter:
                options = ListSQSOptions(
                    region=region, method_name="list_queues", list_param="QueueUrls"
                )
                async for batch in exporter.get_paginated_resources(options):
                    yield batch
