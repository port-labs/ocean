from aiobotocore.session import AioSession

from aws.utils import RegionHelper

ASSUMED_ROLE_RESOURCE_PREFIX = "assumed-role/"


async def get_policy_source_arn(session: AioSession) -> str:
    """Return the IAM principal ARN SimulatePrincipalPolicy accepts for this session."""
    region = await RegionHelper.get_custom_partition_region_or_none(session)
    async with session.create_client("sts", region_name=region) as sts:
        identity = await sts.get_caller_identity()
    return _policy_source_arn_from_caller_arn(str(identity["Arn"]))


def _policy_source_arn_from_caller_arn(arn: str) -> str:
    """Map GetCallerIdentity Arn to a PolicySourceArn for SimulatePrincipalPolicy.

    SimulatePrincipalPolicy only accepts IAM user/group/role ARNs. Assumed-role
    credentials return an STS session ARN
    (``arn:...:sts::ACCOUNT:assumed-role/RoleName/session``), which must be
    rewritten to ``arn:...:iam::ACCOUNT:role/RoleName``. IAM user access keys
    already return an ``iam:`` ARN, so those are left unchanged.
    """
    parts = arn.split(":")
    if len(parts) < 6:
        return arn

    partition, service, account, resource = (
        parts[1],
        parts[2],
        parts[4],
        parts[5],
    )
    if service != "sts" or not resource.startswith(ASSUMED_ROLE_RESOURCE_PREFIX):
        return arn

    role_name = resource.split("/")[1]
    return f"arn:{partition}:iam::{account}:role/{role_name}"
