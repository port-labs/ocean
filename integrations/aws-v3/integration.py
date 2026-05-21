from port_ocean.core.handlers.port_app_config.models import (
    ResourceConfig,
    PortAppConfig,
    Selector,
)
from pydantic import Field, BaseModel
from typing import List
from port_ocean.core.handlers.port_app_config.api import APIPortAppConfig
from port_ocean.core.integrations.base import BaseIntegration


class RegionPolicy(BaseModel):
    allow: List[str] = Field(
        default_factory=list,
        title="Allow Regions",
        description="Regions to exclusively allow e.g. ['us-east-1', 'eu-west-1']. If set, only these regions are synced.",
    )
    deny: List[str] = Field(
        default_factory=list,
        title="Deny Regions",
        description="Regions to exclude e.g. ['us-east-1', 'eu-west-1']. If set, all regions except these are synced.",
    )


class AWSResourceSelector(Selector):
    region_policy: RegionPolicy = Field(
        alias="regionPolicy",
        default_factory=RegionPolicy,
        title="Region Policy",
        description="Controls which AWS regions to include or exclude during resync. "
        "Set 'allow' to sync only specific regions, or 'deny' to exclude specific regions. "
        "If both are empty, all regions are synced. "
        'Example: {"allow": ["us-east-1", "eu-west-1"]} or {"deny": ["cn-north-1"]}.',
    )
    include_actions: List[str] = Field(
        alias="includeActions",
        default_factory=list,
        max_items=3,
        title="Include Actions",
        description="Additional AWS resource types to include when fetching resources (max 3). "
        'EC2 Action Example: [DescribeInstanceStatusAction].',
    )
    max_concurrent_accounts: int = Field(
        alias="maxConcurrentAccounts",
        default=5,
        title="Max Concurrent Accounts",
        description="Maximum number of AWS accounts to process concurrently. "
        "Higher values speed up resync but increase API rate limit pressure and memory usage. "
        "Recommended range: 2-10. Reduce if you encounter throttling errors.",
    )

    def is_region_allowed(self, region: str) -> bool:
        """
        Determines if a given region is allowed based on the query regions policy.
        This method checks the `region_policy` attribute to decide if the specified
        region should be allowed or denied. The policy can contain "allow" and "deny" lists
        which dictate the behavior.

        Scenarios:
        - If `region_policy` is not set or empty, the method returns True, allowing all regions.
        - If the region is listed in the "deny" list of `region_policy`, the method returns False.
        - If the region is listed in the "allow" list of `region_policy`, the method returns True.
        - If the region is not listed in either "allow" or "deny" lists, the method returns False.
        - If the region is listed in both "allow" and "deny" lists, the method returns False.
        - If the policy denies regions but does not explicitly allow any, and the specific region is not in the deny list, then the region is considered allowed.
        - If the policy allows regions but does not explicitly deny any, and the specific region is not in the allow list, then the region is considered denied.
        Args:
            region (str): The region to be checked.

        Returns:
            bool: True if the region is allowed, False otherwise.
        """
        if not self.region_policy.allow and not self.region_policy.deny:
            return True
        if region in self.region_policy.deny:
            return False
        if region in self.region_policy.allow:
            return True
        if self.region_policy.deny and not self.region_policy.allow:
            return True
        if self.region_policy.allow and not self.region_policy.deny:
            return False
        return False


class AWSResourceConfig(ResourceConfig):
    kind: str = Field(
        title="Custom Kind",
        description="Use this to map AWS resources supported by the <a target='_blank' href='https://docs.aws.amazon.com/cloudcontrolapi/latest/userguide/supported-resources.html'>AWS Cloud Control API</a> by setting the kind name to the resource type.\n\nExample: AWS::S3::Bucket",
    )
    selector: AWSResourceSelector = Field(
        title="Selector",
        description="Selector for the AWS resource.",
    )


class AWSPortAppConfig(PortAppConfig):
    resources: List[AWSResourceConfig] = Field(
        default_factory=list,
        title="Resources",
        description="The list of resource configurations to sync from AWS.",
    )  # type: ignore[assignment]


class AWSIntegration(BaseIntegration):
    class AppConfigHandlerClass(APIPortAppConfig):
        CONFIG_CLASS = AWSPortAppConfig
