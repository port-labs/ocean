from typing import Any

import boto3
import json
from port_ocean.context.ocean import ocean
from loguru import logger


# Handles unserializable date properties in the JSON by turning them into a string
def _fix_unserializable_date_properties(obj: Any) -> Any:
    return json.loads(json.dumps(obj, default=str))

def _get_sessions() -> list[boto3.Session]:
    aws_access_key_id = ocean.integration_config.get("aws_access_key_id")
    aws_secret_access_key = ocean.integration_config.get("aws_secret_access_key")
    aws_regions = ocean.integration_config.get("aws_regions")

    aws_sessions = []
    for aws_region in aws_regions:
        aws_sessions.append(boto3.Session(aws_access_key_id=aws_access_key_id, aws_secret_access_key=aws_secret_access_key, region_name=aws_region))
    
    return aws_sessions


# Required
# Listen to the resync event of all the kinds specified in the mapping inside port.
# Called each time with a different kind that should be returned from the source system.
@ocean.on_resync('ec2')
async def on_resync(kind: str) -> list[dict[Any, Any]]:
    sessions = _get_sessions()
    all_instances = []
    for session in sessions:
        region = session.region_name
        try:
            ec2 = session.resource('ec2')
            response = ec2.instances.all()
        except Exception as e:
            logger.error(f"Failed to list EC2 Instance in region: {region}; error {e}")
            break

        ec2_client = session.client('ec2')
        for instance in response:
            described_instance = ec2_client.describe_instances(InstanceIds=[instance.id])
            instance_definition = described_instance["Reservations"][0]["Instances"][0]
            seriliazable_instance = _fix_unserializable_date_properties(instance_definition)
            all_instances.append(seriliazable_instance)
        
    return all_instances

# The same sync logic can be registered for one of the kinds that are available in the mapping in port.
# @ocean.on_resync('project')
# async def resync_project(kind: str) -> list[dict[Any, Any]]:
#     # 1. Get all projects from the source system
#     # 2. Return a list of dictionaries with the raw data of the state
#     return [{"some_project_key": "someProjectValue", ...}]
#
# @ocean.on_resync('issues')
# async def resync_issues(kind: str) -> list[dict[Any, Any]]:
#     # 1. Get all issues from the source system
#     # 2. Return a list of dictionaries with the raw data of the state
#     return [{"some_issue_key": "someIssueValue", ...}]


# Optional
# Listen to the start event of the integration. Called once when the integration starts.
@ocean.on_start()
async def on_start() -> None:
    # Something to do when the integration starts
    # For example create a client to query 3rd party services - GitHub, Jira, etc...
    print("Starting integration")
