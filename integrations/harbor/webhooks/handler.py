"""Webhook processor for Harbor events."""

from __future__ import annotations

import hashlib
import hmac
from typing import Any

try:  # pragma: no cover - used in production when fastapi is available
    from fastapi import Request
except ImportError:  # pragma: no cover - test fallback

    class Request:  # type: ignore
        def __init__(
            self, headers: dict[str, str] | None = None, body: bytes | None = None
        ):
            self.headers = headers or {}
            self._body = body or b""

        async def body(self) -> bytes:
            return self._body


from loguru import logger

from port_ocean.context.ocean import ocean
from port_ocean.core.handlers.port_app_config.models import ResourceConfig
from port_ocean.core.handlers.webhook.abstract_webhook_processor import (
    AbstractWebhookProcessor,
)
from port_ocean.core.handlers.webhook.webhook_event import (
    EventHeaders,
    EventPayload,
    WebhookEvent,
    WebhookEventRawResults,
)

from integrations.harbor.exporters.artifacts import ArtifactsExporter
from integrations.harbor.logging_utils import log_webhook_event
from integrations.harbor.mappers import map_artifact


SUPPORTED_EVENTS = {
    "PUSH_ARTIFACT",
    "DELETE_ARTIFACT",
    "SCANNED_ARTIFACT",
}


def _get_runtime():  # pragma: no cover - thin wrapper for easier testing
    from integrations.harbor.integration import get_runtime as _runtime_getter

    return _runtime_getter()


class HarborWebhookProcessor(AbstractWebhookProcessor):
    """Processes Harbor webhook events and emits delta updates."""

    SIGNATURE_HEADER = "X-Harbor-Signature"
    EVENT_HEADER = "X-Harbor-Event"

    def __init__(self, event: WebhookEvent) -> None:
        super().__init__(event)
        self._runtime = _get_runtime()
        secret = self._runtime.settings.webhook_secret
        self._secret = (
            secret.strip() if isinstance(secret, str) and secret.strip() else None
        )
        self._last_verification = False

    async def should_process_event(self, event: WebhookEvent) -> bool:
        event_type = self._resolve_event_type(event.payload, event.headers)
        if not event_type:
            logger.debug("Ignoring webhook with missing event type")
            return False

        if event_type not in SUPPORTED_EVENTS:
            logger.debug("Received unsupported Harbor event", event_type=event_type)
            return False

        if not event._original_request:
            logger.warning("Webhook event missing original request context, skipping")
            return False

        is_valid = await self._verify_signature(event._original_request)
        self._last_verification = is_valid
        logger.info(
            "Webhook signature verification result",
            verified=is_valid,
            event_type=event_type,
        )
        return is_valid

    async def get_matching_kinds(self, event: WebhookEvent) -> list[str]:
        return ["harbor-artifact"]

    async def authenticate(self, payload: EventPayload, headers: EventHeaders) -> bool:
        # Signature verification is performed in should_process_event, so we can trust the payload here.
        return True

    async def validate_payload(self, payload: EventPayload) -> bool:
        if not isinstance(payload, dict):
            return False

        event_data = payload.get("event_data")
        repository = (event_data or {}).get("repository")
        resources = (event_data or {}).get("resources")

        return (
            repository is not None
            and isinstance(resources, list)
            and all(isinstance(resource, dict) for resource in resources)
        )

    async def handle_event(
        self, payload: EventPayload, resource_config: ResourceConfig
    ) -> WebhookEventRawResults:
        event_type = self._resolve_event_type(payload, self.event.headers)
        if not event_type:
            logger.warning("Unable to resolve event type, skipping")
            return WebhookEventRawResults([], [])

        repository_context = self._extract_repository_context(payload)
        resources = payload.get("event_data", {}).get("resources", [])

        updated: list[dict[str, Any]] = []
        deleted: list[dict[str, Any]] = []

        if event_type in {"PUSH_ARTIFACT", "SCANNED_ARTIFACT"}:
            updated = await self._fetch_artifacts(repository_context, resources)
        elif event_type == "DELETE_ARTIFACT":
            deleted = self._delete_payload(repository_context, resources)

        organization_id = self._runtime.resolve_port_org_id()
        log_webhook_event(
            event_type,
            updated=len(updated),
            deleted=len(deleted),
            verified=self._last_verification,
            organization_id=organization_id,
        )

        return WebhookEventRawResults(
            updated_raw_results=updated, deleted_raw_results=deleted
        )

    def _delete_payload(
        self, repository_context: dict[str, str], resources: list[dict[str, Any]]
    ) -> list[dict[str, Any]]:
        project_name = repository_context["project_name"]
        repository = repository_context["repository_name"]
        repository_path = repository_context["repository_path"]

        deleted: list[dict[str, Any]] = []
        for resource in resources:
            digest = resource.get("digest")
            if not digest:
                continue
            deleted.append(
                {
                    "project_name": project_name,
                    "repository": repository,
                    "repository_path": repository_path,
                    "digest": digest,
                }
            )
        return deleted

    async def _fetch_artifacts(
        self, repository_context: dict[str, str], resources: list[dict[str, Any]]
    ) -> list[dict[str, Any]]:
        digests = [res.get("digest") for res in resources if res.get("digest")]
        tags = [res.get("tag") for res in resources if res.get("tag")]
        settings = self._runtime.settings

        exporter = ArtifactsExporter(
            self._create_client(),
            repositories=[
                {
                    "project_name": repository_context["project_name"],
                    "repository_path": repository_context["repository_path"],
                }
            ],
            digest_filter=digests or None,
            tag_filter=tags or None,
            max_concurrency=settings.max_concurrency,
        )

        artifacts: list[dict[str, Any]] = []
        async for batch in exporter.iter_artifacts():
            for raw_artifact in batch:
                artifacts.append(map_artifact(raw_artifact).as_dict())
        return artifacts

    def _extract_repository_context(self, payload: EventPayload) -> dict[str, str]:
        repository_info = payload.get("event_data", {}).get("repository", {})
        repo_full_name = repository_info.get("repo_full_name")
        namespace = repository_info.get("namespace")
        name = repository_info.get("name")

        if isinstance(repo_full_name, str) and repo_full_name:
            repository_path = repo_full_name
        else:
            repository_path = "/".join(
                part for part in [namespace, name] if isinstance(part, str) and part
            )

        project_name = namespace or (
            repository_path.split("/", 1)[0] if repository_path else ""
        )
        repository_name = name or (
            repository_path.split("/", 1)[-1] if repository_path else ""
        )

        if not repository_path:
            raise ValueError(
                "Repository path could not be determined from webhook payload"
            )

        return {
            "project_name": project_name,
            "repository_name": repository_name,
            "repository_path": repository_path,
        }

    def _resolve_event_type(
        self, payload: EventPayload, headers: EventHeaders
    ) -> str | None:
        header_value = headers.get(self.EVENT_HEADER)
        if header_value:
            return header_value.upper()
        event_type = payload.get("type") or payload.get("event_type")
        if isinstance(event_type, str):
            return event_type.upper()
        return None

    async def _verify_signature(self, request: Request) -> bool:
        if not self._secret:
            logger.warning(
                "No webhook secret configured; accepting Harbor webhook without signature validation"
            )
            return True

        signature_header = request.headers.get(self.SIGNATURE_HEADER)
        if not signature_header:
            logger.error(
                "Missing Harbor signature header", header=self.SIGNATURE_HEADER
            )
            return False

        body = await request.body()
        digest = hmac.new(self._secret.encode(), body, hashlib.sha256).hexdigest()
        expected = f"sha256={digest}"

        is_valid = hmac.compare_digest(
            signature_header, expected
        ) or hmac.compare_digest(signature_header, digest)
        if not is_valid:
            logger.error(
                "harbor.webhook.signature_mismatch",
                expected=expected,
                received=signature_header,
            )
        return is_valid

    def _create_client(self):
        return self._runtime.create_client()
