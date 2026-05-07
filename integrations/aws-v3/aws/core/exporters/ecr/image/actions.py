from typing import Any, Type
from aws.core.interfaces.action import Action, ActionMap
from aws.core.helpers.utils import execute_concurrent_aws_operations


class GetImageDetailsAction(Action):
    """Fetches detailed information about ECR images."""

    async def _execute(self, images: list[dict[str, Any]]) -> list[dict[str, Any]]:
        return await execute_concurrent_aws_operations(
            input_items=images,
            operation_func=self._fetch_image_details,
            get_resource_identifier=lambda img: f"{img['repositoryName']}:{img.get('imageId', {}).get('imageTag', img.get('imageId', {}).get('imageDigest', 'unknown'))}",
            operation_name="image details",
        )

    async def _fetch_image_details(self, image: dict[str, Any]) -> dict[str, Any]:
        # ECR describe_images already provides most details, so we return the image as-is
        # with any additional processing if needed
        return image


class GetImageScanResultsAction(Action):
    """Fetches vulnerability scan results for ECR images."""

    async def _execute(self, images: list[dict[str, Any]]) -> list[dict[str, Any]]:
        return await execute_concurrent_aws_operations(
            input_items=images,
            operation_func=self._fetch_image_scan_results,
            get_resource_identifier=lambda img: f"{img['repositoryName']}:{img.get('imageId', {}).get('imageTag', img.get('imageId', {}).get('imageDigest', 'unknown'))}",
            operation_name="image scan results",
        )

    async def _fetch_image_scan_results(self, image: dict[str, Any]) -> dict[str, Any]:
        try:
            response = await self.client.describe_image_scan_findings(
                repositoryName=image["repositoryName"],
                imageId=image["imageId"]
            )
            return {
                "imageScanFindingsSummary": response.get("imageScanFindingsSummary", {}),
                "imageScanningConfiguration": response.get("imageScanningConfiguration", {}),
            }
        except self.client.exceptions.ClientError as e:
            error_code = e.response.get("Error", {}).get("Code")
            if error_code in ["ScanNotFoundException", "ImageNotFoundException"]:
                return {"imageScanFindingsSummary": {}, "imageScanningConfiguration": {}}
            else:
                raise


class DescribeImagesAction(Action):
    """Processes the initial list of images from AWS."""

    async def _execute(self, images: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Return images as-is from describe_images API call"""
        return images


class EcrImageActionsMap(ActionMap):
    """Groups all actions for ECR images."""

    defaults: list[Type[Action]] = [
        DescribeImagesAction,
        GetImageDetailsAction,
    ]
    options: list[Type[Action]] = [
        GetImageScanResultsAction,
    ]