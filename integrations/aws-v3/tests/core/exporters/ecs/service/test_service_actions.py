import pytest
from unittest.mock import AsyncMock
from aws.core.exporters.ecs.service.actions import DescribeServicesAction


class TestDescribeServicesAction:

    @pytest.mark.asyncio
    async def test_execute_with_valid_service_identifiers(self) -> None:
        """Test describing services with valid identifiers."""
        mock_client = AsyncMock()
        mock_client.describe_services.return_value = {
            "services": [
                {
                    "serviceName": "service1",
                    "serviceArn": "arn:aws:ecs:us-east-1:123456789012:service/cluster1/service1",
                    "clusterArn": "arn:aws:ecs:us-east-1:123456789012:cluster/cluster1",
                    "status": "ACTIVE",
                    "desiredCount": 2,
                    "runningCount": 2,
                }
            ]
        }

        action = DescribeServicesAction(mock_client)
        service_identifiers = [
            {
                "serviceArn": "arn:aws:ecs:us-east-1:123456789012:service/cluster1/service1",
                "clusterArn": "arn:aws:ecs:us-east-1:123456789012:cluster/cluster1",
            }
        ]

        result = await action._execute(service_identifiers)

        assert len(result) == 1
        assert result[0]["serviceName"] == "service1"
        assert result[0]["status"] == "ACTIVE"
        assert result[0]["desiredCount"] == 2
        assert result[0]["runningCount"] == 2

        mock_client.describe_services.assert_called_once_with(
            cluster="arn:aws:ecs:us-east-1:123456789012:cluster/cluster1",
            services=["arn:aws:ecs:us-east-1:123456789012:service/cluster1/service1"],
            include=["TAGS"],
        )

    @pytest.mark.asyncio
    async def test_execute_with_multiple_services_same_cluster(self) -> None:
        """Test describing multiple services from the same cluster."""
        mock_client = AsyncMock()
        mock_client.describe_services.return_value = {
            "services": [
                {
                    "serviceName": "service1",
                    "serviceArn": "arn:aws:ecs:us-east-1:123456789012:service/cluster1/service1",
                    "clusterArn": "arn:aws:ecs:us-east-1:123456789012:cluster/cluster1",
                },
                {
                    "serviceName": "service2",
                    "serviceArn": "arn:aws:ecs:us-east-1:123456789012:service/cluster1/service2",
                    "clusterArn": "arn:aws:ecs:us-east-1:123456789012:cluster/cluster1",
                },
            ]
        }

        action = DescribeServicesAction(mock_client)
        service_identifiers = [
            {
                "serviceArn": "arn:aws:ecs:us-east-1:123456789012:service/cluster1/service1",
                "clusterArn": "arn:aws:ecs:us-east-1:123456789012:cluster/cluster1",
            },
            {
                "serviceArn": "arn:aws:ecs:us-east-1:123456789012:service/cluster1/service2",
                "clusterArn": "arn:aws:ecs:us-east-1:123456789012:cluster/cluster1",
            },
        ]

        result = await action._execute(service_identifiers)

        assert len(result) == 2
        assert result[0]["serviceName"] == "service1"
        assert result[1]["serviceName"] == "service2"

        # Should call describe_services once with both service ARNs for cluster1
        mock_client.describe_services.assert_called_once_with(
            cluster="arn:aws:ecs:us-east-1:123456789012:cluster/cluster1",
            services=[
                "arn:aws:ecs:us-east-1:123456789012:service/cluster1/service1",
                "arn:aws:ecs:us-east-1:123456789012:service/cluster1/service2",
            ],
            include=["TAGS"],
        )

    @pytest.mark.asyncio
    async def test_execute_with_exception_returns_empty_list(self) -> None:
        """Test that exceptions return empty list and are logged."""
        mock_client = AsyncMock()
        mock_client.describe_services.side_effect = Exception("AWS API Error")

        action = DescribeServicesAction(mock_client)
        service_identifiers = [
            {
                "serviceArn": "arn:aws:ecs:us-east-1:123456789012:service/cluster1/service1",
                "clusterArn": "arn:aws:ecs:us-east-1:123456789012:cluster/cluster1",
            }
        ]

        result = await action._execute(service_identifiers)

        assert result == []
        mock_client.describe_services.assert_called_once()
