import json
from typing import Any

from loguru import logger
from utils.misc import (
    CustomProperties,
)
from utils.aws import get_sessions

from port_ocean.core.ocean_types import ASYNC_GENERATOR_RESYNC_TYPE
from utils.aws import _session_manager


def is_global_resource(kind: str) -> bool:
    global_services = [
        "cloudfront",
        "route53",
        "waf",
        "waf-regional",
        "iam",
        "organizations",
    ]
    try:
        service = kind.split("::")[1].lower()
        return service in global_services
    except IndexError:
        return False


def fix_unserializable_date_properties(obj: Any) -> Any:
    return json.loads(json.dumps(obj, default=str))


async def describe_single_resource(
    kind: str, identifier: str, account_id: str | None = None, region: str | None = None
) -> dict[str, str]:
    async for session in get_sessions(account_id, region):
        region = session.region_name
        async with session.client("cloudcontrol") as cloudcontrol:
            response = await cloudcontrol.get_resource(
                TypeName=kind, Identifier=identifier
            )
            resource_description = response.get("ResourceDescription")
            serialized = resource_description.copy()
            serialized.update(
                {
                    "Properties": json.loads(resource_description.get("Properties")),
                }
            )
            return serialized
    return {}


async def resync_cloudcontrol(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    is_global = is_global_resource(kind)
    async for session in get_sessions(None, None, is_global):
        region = session.region_name
        logger.info(f"Resyncing {kind} in region {region}")
        account_id = await _session_manager.find_account_id_by_session(session)
        next_token = None
        while True:
            async with session.client("cloudcontrol") as cloudcontrol:
                params = {
                    "TypeName": kind,
                }
                if next_token:
                    params["NextToken"] = next_token

                response = await cloudcontrol.list_resources(**params)
                next_token = response.get("NextToken")
                resources = response.get("ResourceDescriptions", [])
                if not resources:
                    break
                page_resources = []
                for instance in resources:
                    serialized = instance.copy()
                    serialized.update(
                        {
                            CustomProperties.KIND: kind,
                            CustomProperties.ACCOUNT_ID: account_id,
                            CustomProperties.REGION: region,
                            "Properties": json.loads(instance.get("Properties")),
                        }
                    )
                    page_resources.append(
                        fix_unserializable_date_properties(serialized)
                    )
                yield page_resources

                if not next_token:
                    break
