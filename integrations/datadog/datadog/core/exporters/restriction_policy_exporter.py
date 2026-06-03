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

    @staticmethod
    def _extract_restricted_principals(
        policy: dict[str, Any] | None,
    ) -> tuple[list[str], list[str], list[str]]:
        bindings = ((policy or {}).get("attributes") or {}).get("bindings", [])
        principals = [
            principal
            for binding in bindings
            for principal in binding.get("principals", [])
        ]

        grouped: dict[str, list[str]] = {"user": [], "team": [], "role": []}
        for principal in principals:
            principal_type, _, principal_id = principal.partition(":")
            if principal_id and principal_type in grouped:
                grouped[principal_type].append(principal_id)

        return (
            list(dict.fromkeys(grouped["user"])),
            list(dict.fromkeys(grouped["team"])),
            list(dict.fromkeys(grouped["role"])),
        )

    async def enrich_resource_with_restriction_policy(
        self, resource_type: str, resource: dict[str, Any]
    ) -> dict[str, Any]:
        """Enrich a resource dict with its restriction policy."""
        policy = await self.get_resource(f"{resource_type}:{resource['id']}")
        restricted_users, restricted_teams, restricted_roles = (
            self._extract_restricted_principals(policy)
        )
        resource["__restrictionPolicy"] = policy
        resource["__restrictedUsers"] = restricted_users
        resource["__restrictedTeams"] = restricted_teams
        resource["__restrictedRoles"] = restricted_roles
        return resource
