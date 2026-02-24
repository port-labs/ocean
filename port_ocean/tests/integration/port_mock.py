import json as json_lib
from typing import Any

import httpx

from port_ocean.tests.integration.transport import InterceptTransport


class PortMockResponder:
    """Pre-configured mock for Port API endpoints used during resync.

    Handles auth, integration config, entity upsert (with capture), blueprints,
    entity search, migrations, and resync state updates.
    """

    def __init__(
        self,
        mapping_config: dict[str, Any],
        integration_identifier: str = "test-integration",
        blueprints: dict[str, dict[str, Any]] | None = None,
    ) -> None:
        self.transport = InterceptTransport(strict=False)
        self.upserted_entities: list[dict[str, Any]] = []
        self.deleted_entity_ids: list[str] = []
        self.mapping_config = mapping_config
        self.integration_identifier = integration_identifier
        self.blueprints = blueprints or {}
        self._setup_routes()

    def _setup_routes(self) -> None:
        # Auth
        self.transport.add_route(
            "POST",
            "/v1/auth/access_token",
            {
                "json": {
                    "accessToken": "test-token",
                    "expiresIn": 999999999,
                    "tokenType": "Bearer",
                }
            },
        )

        # Integration config (returns mapping config)
        self.transport.add_route(
            None,
            "/v1/integration/",
            self._handle_integration,
        )

        # Entity search — must be before generic blueprints route
        self.transport.add_route(
            "POST",
            "/v1/entities/search",
            {"json": {"ok": True, "entities": []}},
        )

        # Bulk entity upsert — must be before generic blueprints route
        self.transport.add_route(
            "POST",
            "/entities/bulk",
            self._handle_bulk_upsert,
        )

        # Single entity upsert (fallback)
        self.transport.add_route(
            "POST",
            "/v1/blueprints/",
            self._handle_single_upsert,
        )

        # Bulk delete
        self.transport.add_route(
            "DELETE",
            "/all-entities",
            {"json": {"migrationId": "test-migration"}},
        )

        # Migration status
        self.transport.add_route(
            "GET",
            "/v1/migrations/",
            {
                "json": {
                    "migration": {
                        "id": "test-migration",
                        "status": "COMPLETE",
                        "actor": "test",
                        "sourceBlueprint": "test",
                        "mapping": {},
                    }
                }
            },
        )

        # Organization feature flags
        self.transport.add_route(
            "GET",
            "/v1/organization",
            {"json": {"organization": {"featureFlags": []}}},
        )

        # Blueprint get/patch — generic catch-all for blueprints
        self.transport.add_route(
            None,
            "/v1/blueprints/",
            self._handle_blueprint,
        )

    def _handle_integration(self, request: httpx.Request) -> dict[str, Any]:
        return {
            "json": {
                "integration": {
                    "identifier": self.integration_identifier,
                    "integrationType": "test",
                    "resyncState": {
                        "status": "completed",
                    },
                    "config": self.mapping_config,
                    "installationType": "OnPrem",
                    "_orgId": "test-org",
                    "_id": "test-id",
                    "createdBy": "test",
                    "updatedBy": "test",
                    "createdAt": "2024-01-01T00:00:00.000Z",
                    "updatedAt": "2024-01-01T00:00:00.000Z",
                    "clientId": "",
                    "logAttributes": {
                        "ingestId": "test-ingest",
                        "ingestUrl": "http://localhost:5555/logs/test",
                    },
                }
            }
        }

    def _handle_bulk_upsert(self, request: httpx.Request) -> dict[str, Any]:
        """Handle POST /v1/blueprints/{blueprint}/entities/bulk

        Request body: {"entities": [...]}
        Response: {"entities": [{"index": 0, ...}, ...], "errors": []}
        """
        body = json_lib.loads(request.content.decode("utf-8"))
        entities = body.get("entities", [])

        response_entities = []
        for i, entity in enumerate(entities):
            self.upserted_entities.append(entity)
            response_entities.append({"index": i, "status": "SUCCESS"})

        return {
            "json": {
                "entities": response_entities,
                "errors": [],
            }
        }

    def _handle_single_upsert(self, request: httpx.Request) -> dict[str, Any]:
        """Handle POST /v1/blueprints/{blueprint}/entities (single upsert)."""
        body = json_lib.loads(request.content.decode("utf-8"))
        self.upserted_entities.append(body)
        return {"json": {"ok": True, "entity": body}}

    def _handle_blueprint(self, request: httpx.Request) -> dict[str, Any]:
        url_path = str(request.url.path)
        parts = url_path.strip("/").split("/")
        blueprint_id = parts[-1] if len(parts) >= 3 else "unknown"

        blueprint = self.blueprints.get(
            blueprint_id,
            {
                "identifier": blueprint_id,
                "title": blueprint_id,
                "icon": "Blueprint",
                "schema": {"properties": {}},
                "relations": {},
            },
        )
        return {"json": {"blueprint": blueprint}}
