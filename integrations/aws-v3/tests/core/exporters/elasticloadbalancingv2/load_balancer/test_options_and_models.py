import pytest
from pydantic.v1 import ValidationError

from aws.core.exporters.elasticloadbalancingv2.load_balancer.models import (
    LoadBalancer,
    LoadBalancerProperties,
    SingleLoadBalancerRequest,
    PaginatedLoadBalancerRequest,
)


class TestSingleLoadBalancerRequest:

    def test_initialization_with_required_fields(self) -> None:
        options = SingleLoadBalancerRequest(
            region="us-east-1",
            account_id="123456789012",
            load_balancer_arn="arn:aws:elasticloadbalancing:us-east-1:123456789012:loadbalancer/app/my-lb/1234567890abcdef",
        )
        assert options.region == "us-east-1"
        assert options.account_id == "123456789012"
        assert options.load_balancer_arn == "arn:aws:elasticloadbalancing:us-east-1:123456789012:loadbalancer/app/my-lb/1234567890abcdef"
        assert options.include == []

    def test_initialization_with_include(self) -> None:
        include_list = ["DescribeTagsAction"]
        options = SingleLoadBalancerRequest(
            region="eu-west-1",
            account_id="123456789012",
            load_balancer_arn="arn:aws:elasticloadbalancing:eu-west-1:123456789012:loadbalancer/app/my-lb/1234567890abcdef",
            include=include_list,
        )
        assert options.include == include_list

    def test_missing_required_region(self) -> None:
        with pytest.raises(ValidationError) as exc_info:
            SingleLoadBalancerRequest(
                account_id="123456789012",
                load_balancer_arn="arn:aws:elasticloadbalancing:us-east-1:123456789012:loadbalancer/app/my-lb/1234567890abcdef",
            )  # type: ignore
        assert "region" in str(exc_info.value)

    def test_missing_required_load_balancer_arn(self) -> None:
        with pytest.raises(ValidationError) as exc_info:
            SingleLoadBalancerRequest(
                region="us-east-1",
                account_id="123456789012",
            )  # type: ignore
        assert "load_balancer_arn" in str(exc_info.value)


class TestPaginatedLoadBalancerRequest:

    def test_inheritance(self) -> None:
        options = PaginatedLoadBalancerRequest(
            region="us-west-2", account_id="123456789012"
        )
        assert isinstance(options, PaginatedLoadBalancerRequest)

    def test_initialization_with_required_fields(self) -> None:
        options = PaginatedLoadBalancerRequest(
            region="us-east-1", account_id="123456789012"
        )
        assert options.region == "us-east-1"
        assert options.account_id == "123456789012"
        assert options.include == []

    def test_initialization_with_include(self) -> None:
        include_list = ["DescribeTagsAction"]
        options = PaginatedLoadBalancerRequest(
            region="ap-southeast-1", account_id="123456789012", include=include_list
        )
        assert options.include == include_list


class TestLoadBalancerProperties:

    def test_initialization_empty(self) -> None:
        properties = LoadBalancerProperties()
        assert properties.LoadBalancerArn == ""
        assert properties.LoadBalancerName == ""
        assert properties.DNSName is None
        assert properties.Scheme is None
        assert properties.Type is None
        assert properties.State is None
        assert properties.VpcId is None
        assert properties.IpAddressType is None
        assert properties.Tags is None

    def test_initialization_with_properties(self) -> None:
        properties = LoadBalancerProperties(
            LoadBalancerArn="arn:aws:elasticloadbalancing:us-east-1:123456789012:loadbalancer/app/my-lb/1234567890abcdef",
            LoadBalancerName="my-lb",
            DNSName="my-lb-1234567890abcdef.us-east-1.elb.amazonaws.com",
            Scheme="internet-facing",
            Type="application",
            State={"Code": "active"},
            VpcId="vpc-12345678",
            IpAddressType="ipv4",
            AvailabilityZones=[{"ZoneName": "us-east-1a", "SubnetId": "subnet-12345678"}],
            SecurityGroups=["sg-12345678"],
            Tags=[{"Key": "Environment", "Value": "production"}],
        )
        assert properties.LoadBalancerName == "my-lb"
        assert properties.Scheme == "internet-facing"
        assert properties.Type == "application"
        assert properties.State == {"Code": "active"}
        assert properties.VpcId == "vpc-12345678"
        assert properties.Tags == [{"Key": "Environment", "Value": "production"}]

    def test_dict_exclude_none(self) -> None:
        properties = LoadBalancerProperties(
            LoadBalancerArn="arn:aws:elasticloadbalancing:us-east-1:123456789012:loadbalancer/app/my-lb/1234567890abcdef",
            LoadBalancerName="my-lb",
            Type="application",
        )
        result = properties.dict(exclude_none=True)
        assert result["LoadBalancerName"] == "my-lb"
        assert result["Type"] == "application"
        assert "DNSName" not in result
        assert "Scheme" not in result


class TestLoadBalancer:

    def test_initialization(self) -> None:
        lb = LoadBalancer(
            Properties=LoadBalancerProperties(
                LoadBalancerArn="arn:aws:elasticloadbalancing:us-east-1:123456789012:loadbalancer/app/my-lb/1234567890abcdef",
                LoadBalancerName="my-lb",
            )
        )
        assert lb.Type == "AWS::ElasticLoadBalancingV2::LoadBalancer"
        assert lb.Properties.LoadBalancerName == "my-lb"

    def test_type_is_fixed(self) -> None:
        lb1 = LoadBalancer(
            Properties=LoadBalancerProperties(LoadBalancerName="lb-1")
        )
        lb2 = LoadBalancer(
            Properties=LoadBalancerProperties(LoadBalancerName="lb-2")
        )
        assert lb1.Type == "AWS::ElasticLoadBalancingV2::LoadBalancer"
        assert lb2.Type == "AWS::ElasticLoadBalancingV2::LoadBalancer"

    def test_dict_exclude_none(self) -> None:
        lb = LoadBalancer(
            Properties=LoadBalancerProperties(
                LoadBalancerArn="arn:aws:elasticloadbalancing:us-east-1:123456789012:loadbalancer/app/my-lb/1234567890abcdef",
                LoadBalancerName="my-lb",
            )
        )
        data = lb.dict(exclude_none=True)
        assert data["Type"] == "AWS::ElasticLoadBalancingV2::LoadBalancer"
        assert data["Properties"]["LoadBalancerName"] == "my-lb"

    def test_properties_default_factory(self) -> None:
        lb1 = LoadBalancer(
            Properties=LoadBalancerProperties(LoadBalancerName="lb-1")
        )
        lb2 = LoadBalancer(
            Properties=LoadBalancerProperties(LoadBalancerName="lb-2")
        )
        assert lb1.Properties is not lb2.Properties
        assert lb1.Properties.LoadBalancerName == "lb-1"
        assert lb2.Properties.LoadBalancerName == "lb-2"
