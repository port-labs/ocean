import hmac
import hashlib
from typing import Any, Optional
from loguru import logger
from port_ocean.context.ocean import ocean
from harbor.clients import HarborClient


class HarborWebhookHandler:
    def __init__(self, webhook_secret: Optional[str] = None):
        self.webhook_secret = webhook_secret
        self.logger = logger

    def verify_signature(self, signature: str, payload: bytes) -> bool:
        if not self.webhook_secret:
            return True

        expected_signature = hmac.new(self.webhook_secret.encode(), payload, hashlib.sha256).hexdigest()

        return hmac.compare_digest(signature, expected_signature)

    async def handle_webhook_event(self, event_type: str, event_data: dict[str, Any]) -> None:
        self.logger.info(f"Received webhook event: {event_type}")

        match event_type:
            case "PUSH_ARTIFACT":
                await self._handle_push_artifact(event_data)
            case "DELETE_ARTIFACT":
                await self._handle_delete_artifact(event_data)
            case "SCANNING_COMPLETED":
                await self._handle_scanning_completed(event_data)
            case "SCANNING_FAILED":
                await self._handle_scanning_failed(event_data)
            case _:
                self.logger.debug(f"Unhandled event type: {event_type}")

    async def _handle_push_artifact(self, event_data: dict[str, Any]) -> None:
        repository_data = event_data.get("repository", {})
        project_name = repository_data.get("namespace")
        repo_name = repository_data.get("name")
        resources = event_data.get("resources", [])

        if not project_name or not repo_name:
            self.logger.warning("Missing project or repository name in event")
            return

        if not resources:
            self.logger.warning("No resources in PUSH_ARTIFACT event")
            return

        harbor_client = self._get_harbor_client()

        for resource in resources:
            digest = resource.get("digest")
            if not digest:
                continue

            try:
                artifact = await harbor_client.get_artifact(
                    project_name, repo_name, digest, with_scan_overview=True, with_tag=True, with_label=True
                )
                if artifact:
                    await self._upsert_artifact(project_name, repo_name, artifact)
                    self.logger.info(f"Processed PUSH_ARTIFACT for {project_name}/{repo_name}@{digest[:12]}")

            except Exception as e:
                self.logger.error(f"Failed to handle PUSH_ARTIFACT for {digest[:12]}: {e}")

    async def _handle_delete_artifact(self, event_data: dict[str, Any]) -> None:
        resources = event_data.get("resources", [])

        for resource in resources:
            digest = resource.get("digest", "")[:12]
            repo_url = resource.get("resource_url", "")

            if "/" in repo_url:
                repo_name = repo_url.split("/")[-1].split(":")[0]
                identifier = f"{repo_name}-{digest}".replace("/", "-")

                try:
                    await ocean.unregister_raw("artifact", [{"identifier": identifier}])
                    self.logger.info(f"Deleted artifact: {identifier}")
                except Exception as e:
                    self.logger.error(f"Failed to delete artifact {identifier}: {e}")

    async def _handle_scanning_completed(self, event_data: dict[str, Any]) -> None:
        repository_data = event_data.get("repository", {})
        project_name = repository_data.get("namespace")
        repo_name = repository_data.get("name")
        resources = event_data.get("resources", [])

        if not project_name or not repo_name:
            self.logger.warning("Missing project or repository name in scanning event")
            return

        if not resources:
            self.logger.warning("No resources in SCANNING_COMPLETED event")
            return

        harbor_client = self._get_harbor_client()

        for resource in resources:
            digest = resource.get("digest")
            if not digest:
                continue

            try:
                artifact = await harbor_client.get_artifact(
                    project_name, repo_name, digest, with_scan_overview=True, with_tag=True, with_label=True
                )
                if artifact:
                    await self._upsert_artifact(project_name, repo_name, artifact)
                    self.logger.info(f"Updated scan results for {project_name}/{repo_name}@{digest[:12]}")

            except Exception as e:
                self.logger.error(f"Failed to update scan results for {digest[:12]}: {e}")

    async def _handle_scanning_failed(self, event_data: dict[str, Any]) -> None:
        repository_data = event_data.get("repository", {})
        project_name = repository_data.get("namespace")
        repo_name = repository_data.get("name")

        self.logger.warning(f"Scanning failed for {project_name}/{repo_name}")

    async def _upsert_artifact(self, project_name: str, repo_name: str, artifact: dict[str, Any]) -> None:
        digest = artifact.get("digest")
        if not digest or not isinstance(digest, str):
            self.logger.warning("Artifact missing valid digest, skipping")
            return

        scan_overview = artifact.get("scan_overview") or {}
        scan_data: dict[str, Any] = next(iter(scan_overview.values()), {}) if scan_overview else {}
        summary_data = scan_data.get("summary") or {}
        summary = summary_data.get("summary") or {}

        # Safely extract tag names
        raw_tags = artifact.get("tags") or []
        tags = [tag.get("name") for tag in raw_tags if isinstance(tag, dict) and tag.get("name")]

        # Safely extract label names
        raw_labels = artifact.get("labels") or []
        labels = [label.get("name") for label in raw_labels if isinstance(label, dict) and label.get("name")]

        entity = {
            "identifier": f"{project_name}-{repo_name}-{digest[:12]}".replace("/", "-"),
            "title": f"{project_name}/{repo_name}:{tags[0] if tags else 'untagged'}",
            "properties": {
                "digest": digest,
                "size": artifact.get("size", 0),
                "pushTime": artifact.get("push_time"),
                "pullTime": artifact.get("pull_time"),
                "tags": tags,
                "labels": labels,
                "scanStatus": scan_data.get("scan_status"),
                "scanSeverity": scan_data.get("severity"),
                "vulnerabilityCritical": summary.get("Critical", 0),
                "vulnerabilityHigh": summary.get("High", 0),
                "vulnerabilityMedium": summary.get("Medium", 0),
                "vulnerabilityLow": summary.get("Low", 0),
                "vulnerabilityTotal": sum(summary.values()) if summary else 0,
            },
            "relations": {"repository": f"{project_name}-{repo_name}".replace("/", "-")},
        }

        await ocean.register_raw("artifact", [entity])

    def _get_harbor_client(self) -> HarborClient:
        return HarborClient(
            harbor_host=ocean.integration_config["harbor_host"],
            harbor_username=ocean.integration_config["harbor_username"],
            harbor_password=ocean.integration_config["harbor_password"],
            verify_ssl=ocean.integration_config.get("verify_ssl", True),
        )
