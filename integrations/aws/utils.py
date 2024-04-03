import enum
import json
from typing import Any, AsyncIterator
import boto3
from loguru import logger

ASYNC_GENERATOR_RESYNC_TYPE = AsyncIterator[list[dict[Any, Any]]]

class ResourceKindsWithSpecialHandling(enum.StrEnum):
    """
    Resource kinds with special handling
    These resource kinds are handled separately from the other resource kinds
    """

    CLOUDRESOURCE = "cloudresource"
    EC2 = "AWS::EC2::Instance"
    CLOUDFORMATION = "cloudformation"
    LOADBALANCER = "loadbalancer"
    ELASTICACHE = "elasticache"
    ACM = "acm"

def _fix_unserializable_date_properties(obj: Any) -> Any:
    """
    Handles unserializable date properties in the JSON by turning them into a string
    """
    return json.loads(json.dumps(obj, default=str))

def _describe_resources(sessions: list[boto3.Session], service_name: str, describe_method: str, list_param: str, marker_param: str = "NextToken") -> ASYNC_GENERATOR_RESYNC_TYPE:
    for session in sessions:
        region = session.region_name
        next_token = None
        while True:
            try:
                all_resources = []
                client = session.client(service_name)
                if next_token:
                    pointer_param = marker_param if marker_param == "NextToken" else "Marker"
                    response = getattr(client, describe_method)(**{pointer_param: next_token})
                else:
                    response = getattr(client, describe_method)()
                next_token = response.get(marker_param)
                for resource in response.get(list_param, []):
                    all_resources.append(_fix_unserializable_date_properties(resource))
                yield all_resources
            except Exception as e:
                logger.error(f"Failed to list resources in region: {region}; error {e}")
                break
            if not next_token:
                break