from typing import Any

from datadog.core.exporters.base_exporter import SingleResourceExporter


class RestrictionPolicyExporter(SingleResourceExporter[str]):
    async def get_resource(self, resource_id: str) -> dict[str, Any] | None:
        """Get the restriction policy for a specific resource.
        Docs: https://docs.datadoghq.com/api/latest/restriction-policies/
        Args:
            resource_id: Identifier formatted as {type}:{id} (e.g. "slo:abc123")
        """
        url = f"{self.client.api_url}/api/v2/restriction_policy/{resource_id}"
        result = await self.client.send_api_request(url)
        return result.get("data")
