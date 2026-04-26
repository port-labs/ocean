import pytest
from pydantic import ValidationError
from datetime import datetime

from aws.core.exporters.elasticache.cluster.models import (
    CacheCluster,
    CacheClusterProperties,
    SingleCacheClusterRequest,
    PaginatedCacheClusterRequest,
)


class TestSingleCacheClusterRequest:

    def test_initialization_with_required_fields(self) -> None:
        options = SingleCacheClusterRequest(
            region="us-west-2", account_id="123456789012", cache_cluster_id="cluster-1"
        )
        assert options.region == "us-west-2"
        assert options.account_id == "123456789012"
        assert options.cache_cluster_id == "cluster-1"
        assert options.include == []

    def test_initialization_with_all_fields(self) -> None:
        include_list = ["ListTagsForResourceAction"]
        options = SingleCacheClusterRequest(
            region="eu-central-1",
            account_id="123456789012",
            cache_cluster_id="cluster-2",
            include=include_list,
        )
        assert options.region == "eu-central-1"
        assert options.account_id == "123456789012"
        assert options.cache_cluster_id == "cluster-2"
        assert options.include == include_list

    def test_missing_required_region(self) -> None:
        with pytest.raises(ValidationError) as exc_info:
            SingleCacheClusterRequest(
                account_id="123456789012", cache_cluster_id="cluster-1"
            )  # type: ignore
        assert "region" in str(exc_info.value)

    def test_missing_required_cache_cluster_id(self) -> None:
        with pytest.raises(ValidationError) as exc_info:
            SingleCacheClusterRequest(
                region="us-east-1", account_id="123456789012"
            )  # type: ignore
        assert "cache_cluster_id" in str(exc_info.value)

    def test_empty_include_list(self) -> None:
        options = SingleCacheClusterRequest(
            region="us-east-1",
            account_id="123456789012",
            cache_cluster_id="cluster-3",
            include=[],
        )
        assert options.region == "us-east-1"
        assert options.include == []

    def test_include_list_validation(self) -> None:
        options = SingleCacheClusterRequest(
            region="ap-southeast-1",
            account_id="123456789012",
            cache_cluster_id="cluster-3",
            include=["ListTagsForResourceAction", "DescribeCacheClustersAction"],
        )
        assert len(options.include) == 2
        assert "ListTagsForResourceAction" in options.include
        assert "DescribeCacheClustersAction" in options.include


class TestPaginatedCacheClusterRequest:

    def test_inheritance(self) -> None:
        options = PaginatedCacheClusterRequest(
            region="us-west-2", account_id="123456789012"
        )
        assert isinstance(options, PaginatedCacheClusterRequest)

    def test_initialization_with_required_fields(self) -> None:
        options = PaginatedCacheClusterRequest(
            region="us-east-1", account_id="123456789012"
        )
        assert options.region == "us-east-1"
        assert options.account_id == "123456789012"
        assert options.include == []

    def test_initialization_with_include(self) -> None:
        include_list = ["ListTagsForResourceAction"]
        options = PaginatedCacheClusterRequest(
            region="ap-southeast-2", account_id="123456789012", include=include_list
        )
        assert options.region == "ap-southeast-2"
        assert options.account_id == "123456789012"
        assert options.include == include_list


class TestCacheClusterProperties:

    def test_initialization_empty(self) -> None:
        properties = CacheClusterProperties()
        assert properties.CacheClusterId == ""
        assert properties.ARN == ""
        assert properties.Engine == ""
        assert properties.CacheNodeType == ""
        assert properties.CacheClusterStatus == ""
        assert properties.NumCacheNodes == 0
        assert properties.TransitEncryptionEnabled is False
        assert properties.AtRestEncryptionEnabled is False

    def test_initialization_with_properties(self) -> None:
        properties = CacheClusterProperties(
            CacheClusterId="my-cluster",
            CacheNodeType="cache.t3.micro",
            Engine="redis",
            CacheClusterStatus="available",
            NumCacheNodes=1,
            TransitEncryptionEnabled=True,
            AtRestEncryptionEnabled=True,
            TagList=[{"Key": "Environment", "Value": "test"}],
        )
        assert properties.CacheClusterId == "my-cluster"
        assert properties.CacheNodeType == "cache.t3.micro"
        assert properties.Engine == "redis"
        assert properties.CacheClusterStatus == "available"
        assert properties.NumCacheNodes == 1
        assert properties.TransitEncryptionEnabled is True
        assert properties.AtRestEncryptionEnabled is True
        assert properties.TagList == [{"Key": "Environment", "Value": "test"}]

    def test_dict_exclude_none(self) -> None:
        properties = CacheClusterProperties(
            CacheClusterId="cluster-123",
            Engine="memcached",
            TagList=[{"Key": "Project", "Value": "demo"}],
        )
        result = properties.dict(exclude_none=True)
        assert result["CacheClusterId"] == "cluster-123"
        assert result["Engine"] == "memcached"
        assert result["TagList"] == [{"Key": "Project", "Value": "demo"}]
        assert "CacheNodeType" in result
        assert result["CacheNodeType"] == ""

    def test_all_properties_assignment(self) -> None:
        properties = CacheClusterProperties(
            CacheClusterId="my-redis-cluster",
            ARN="arn:aws:elasticache:us-west-2:123456789012:cluster:my-redis-cluster",
            CacheNodeType="cache.r6g.large",
            Engine="redis",
            EngineVersion="7.0",
            CacheClusterStatus="available",
            NumCacheNodes=1,
            PreferredAvailabilityZone="us-west-2a",
            CacheClusterCreateTime=datetime(2023, 1, 1, 0, 0, 0),
            PreferredMaintenanceWindow="sun:05:00-sun:06:00",
            PendingModifiedValues={},
            CacheSecurityGroups=[],
            CacheParameterGroup={"CacheParameterGroupName": "default.redis7"},
            CacheSubnetGroupName="my-subnet-group",
            CacheNodes=[
                {
                    "CacheNodeId": "0001",
                    "CacheNodeStatus": "available",
                    "Endpoint": {
                        "Address": "my-redis-cluster.abc123.usw2.cache.amazonaws.com",
                        "Port": 6379,
                    },
                }
            ],
            AutoMinorVersionUpgrade=True,
            SecurityGroups=[{"SecurityGroupId": "sg-12345678", "Status": "active"}],
            ReplicationGroupId="my-replication-group",
            SnapshotRetentionLimit=7,
            SnapshotWindow="03:00-04:00",
            AuthTokenEnabled=True,
            TransitEncryptionEnabled=True,
            AtRestEncryptionEnabled=True,
            ReplicationGroupLogDeliveryEnabled=False,
            LogDeliveryConfigurations=[],
            NetworkType="ipv4",
            IpDiscovery="ipv4",
            TransitEncryptionMode="required",
            TagList=[{"Key": "Name", "Value": "my-redis-cluster"}],
        )

        assert properties.CacheClusterId == "my-redis-cluster"
        assert properties.Engine == "redis"
        assert properties.CacheNodeType == "cache.r6g.large"
        assert properties.NumCacheNodes == 1
        assert properties.TransitEncryptionEnabled is True
        assert properties.AtRestEncryptionEnabled is True
        assert properties.TagList == [{"Key": "Name", "Value": "my-redis-cluster"}]

    def test_memcached_configuration_endpoint(self) -> None:
        properties = CacheClusterProperties(
            CacheClusterId="my-memcached-cluster",
            Engine="memcached",
            NumCacheNodes=2,
            ConfigurationEndpoint={
                "Address": "my-memcached-cluster.cfg.usw2.cache.amazonaws.com",
                "Port": 11211,
            },
        )
        assert properties.Engine == "memcached"
        assert properties.NumCacheNodes == 2
        assert properties.ConfigurationEndpoint is not None
        assert "cfg" in properties.ConfigurationEndpoint["Address"]


class TestCacheCluster:

    def test_initialization_with_identifier(self) -> None:
        cache_cluster = CacheCluster(
            Properties=CacheClusterProperties(CacheClusterId="cluster-1")
        )
        assert cache_cluster.Type == "AWS::ElastiCache::Cluster"
        assert cache_cluster.Properties.CacheClusterId == "cluster-1"

    def test_initialization_with_properties(self) -> None:
        properties = CacheClusterProperties(
            CacheClusterId="cluster-2",
            CacheNodeType="cache.t3.small",
            Engine="redis",
            NumCacheNodes=1,
        )
        cache_cluster = CacheCluster(Properties=properties)
        assert cache_cluster.Properties == properties
        assert cache_cluster.Properties.CacheClusterId == "cluster-2"
        assert cache_cluster.Properties.CacheNodeType == "cache.t3.small"
        assert cache_cluster.Properties.Engine == "redis"
        assert cache_cluster.Properties.NumCacheNodes == 1

    def test_type_is_fixed(self) -> None:
        cluster1 = CacheCluster(
            Properties=CacheClusterProperties(CacheClusterId="cluster-1")
        )
        cluster2 = CacheCluster(
            Properties=CacheClusterProperties(CacheClusterId="cluster-2")
        )
        assert cluster1.Type == "AWS::ElastiCache::Cluster"
        assert cluster2.Type == "AWS::ElastiCache::Cluster"

    def test_dict_exclude_none(self) -> None:
        cache_cluster = CacheCluster(
            Properties=CacheClusterProperties(CacheClusterId="cluster-1")
        )
        data = cache_cluster.dict(exclude_none=True)
        assert data["Type"] == "AWS::ElastiCache::Cluster"
        assert data["Properties"]["CacheClusterId"] == "cluster-1"

    def test_properties_default_factory(self) -> None:
        cluster1 = CacheCluster(
            Properties=CacheClusterProperties(CacheClusterId="cluster-1")
        )
        cluster2 = CacheCluster(
            Properties=CacheClusterProperties(CacheClusterId="cluster-2")
        )
        assert cluster1.Properties is not cluster2.Properties
        assert cluster1.Properties.CacheClusterId == "cluster-1"
        assert cluster2.Properties.CacheClusterId == "cluster-2"

    def test_complex_properties_serialization(self) -> None:
        properties = CacheClusterProperties(
            CacheClusterId="cluster-complex",
            CacheNodes=[
                {
                    "CacheNodeId": "0001",
                    "CacheNodeStatus": "available",
                    "Endpoint": {
                        "Address": "cluster-complex.abc123.usw2.cache.amazonaws.com",
                        "Port": 6379,
                    },
                }
            ],
            SecurityGroups=[
                {"SecurityGroupId": "sg-12345678", "Status": "active"},
            ],
            TagList=[
                {"Key": "Environment", "Value": "production"},
                {"Key": "Project", "Value": "web-app"},
            ],
        )
        cache_cluster = CacheCluster(Properties=properties)

        data = cache_cluster.dict(exclude_none=True)
        assert (
            data["Properties"]["CacheNodes"][0]["Endpoint"]["Address"]
            == "cluster-complex.abc123.usw2.cache.amazonaws.com"
        )
        assert data["Properties"]["CacheNodes"][0]["Endpoint"]["Port"] == 6379
        assert len(data["Properties"]["SecurityGroups"]) == 1
        assert len(data["Properties"]["TagList"]) == 2
