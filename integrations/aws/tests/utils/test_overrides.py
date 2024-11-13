import unittest
from utils.overrides import AWSDescribeResourcesSelector, RegionPolicy


class TestAWSDescribeResourcesSelector(unittest.TestCase):

    def test_is_region_allowed_no_policy(self) -> None:
        selector = AWSDescribeResourcesSelector(query="test")
        self.assertTrue(selector.is_region_allowed("us-east-1"))

    def test_is_region_allowed_deny_policy(self) -> None:
        region_policy = RegionPolicy(deny=["us-east-1"])
        selector = AWSDescribeResourcesSelector(
            query="test", regionPolicy=region_policy
        )
        self.assertFalse(selector.is_region_allowed("us-east-1"))
        self.assertTrue(selector.is_region_allowed("us-west-2"))

    def test_is_region_allowed_allow_policy(self) -> None:
        region_policy = RegionPolicy(allow=["us-west-2"])
        selector = AWSDescribeResourcesSelector(
            query="test", regionPolicy=region_policy
        )
        self.assertTrue(selector.is_region_allowed("us-west-2"))
        self.assertFalse(selector.is_region_allowed("us-east-1"))

    def test_is_region_allowed_both_policies(self) -> None:
        region_policy = RegionPolicy(allow=["us-west-2"], deny=["us-east-1"])
        selector = AWSDescribeResourcesSelector(
            query="test", regionPolicy=region_policy
        )
        self.assertFalse(selector.is_region_allowed("us-east-1"))
        self.assertTrue(selector.is_region_allowed("us-west-2"))
        self.assertFalse(selector.is_region_allowed("eu-central-1"))

    def test_is_region_allowed_conflicting_policies(self) -> None:
        region_policy = RegionPolicy(allow=["us-east-1"], deny=["us-east-1"])
        selector = AWSDescribeResourcesSelector(
            query="test", regionPolicy=region_policy
        )
        self.assertFalse(selector.is_region_allowed("us-east-1"))

    def test_is_region_allowed_deny_only(self) -> None:
        region_policy = RegionPolicy(deny=["us-east-1", "us-west-2"])
        selector = AWSDescribeResourcesSelector(
            query="test", regionPolicy=region_policy
        )
        self.assertFalse(selector.is_region_allowed("us-east-1"))
        self.assertFalse(selector.is_region_allowed("us-west-2"))
        self.assertTrue(selector.is_region_allowed("eu-central-1"))

    def test_is_region_allowed_allow_only(self) -> None:
        region_policy = RegionPolicy(allow=["us-east-1", "us-west-2"])
        selector = AWSDescribeResourcesSelector(
            query="test", regionPolicy=region_policy
        )
        self.assertTrue(selector.is_region_allowed("us-east-1"))
        self.assertTrue(selector.is_region_allowed("us-west-2"))
        self.assertFalse(selector.is_region_allowed("eu-central-1"))
