import json as json_lib
from typing import Any
from urllib.parse import unquote_plus

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
        search_entities_response: list[dict[str, Any]] | None = None,
    ) -> None:
        self.transport = InterceptTransport(strict=False)
        self.upserted_entities: list[dict[str, Any]] = []
        self.deleted_entity_ids: list[str] = []
        self.deleted_entities: list[dict[str, Any]] = []
        self.mapping_config = mapping_config
        self.integration_identifier = integration_identifier
        self.blueprints = blueprints or {}
        self.search_entities_response = search_entities_response or []
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
            self._handle_search_entities,
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

        # Single entity delete — must be before bulk delete route
        # Matches: DELETE /v1/blueprints/{blueprint}/entities/{identifier}
        self.transport.add_route(
            "DELETE",
            r"/v1/blueprints/[^/]+/entities/",
            self._handle_delete_entity,
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

        # Metrics endpoints - must be before generic integration route
        self.transport.add_route(
            "PUT",
            "/syncMetrics",
            {"json": {"ok": True}},
        )

        self.transport.add_route(
            "POST",
            "/syncMetrics",
            {"json": {"ok": True}},
        )

        # Blueprint get/patch — generic catch-all for blueprints
        self.transport.add_route(
            None,
            "/v1/blueprints/",
            self._handle_blueprint,
        )

    def _handle_search_entities(self, request: httpx.Request) -> dict[str, Any]:
        """Handle POST /v1/entities/search — returns entities for reconciliation diff."""
        return {"json": {"ok": True, "entities": self.search_entities_response}}

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
                    "metricAttributes": {
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

    def _handle_delete_entity(self, request: httpx.Request) -> dict[str, Any]:
        """Handle DELETE /v1/blueprints/{blueprint}/entities/{identifier}

        Extracts blueprint and identifier from URL and records the deletion.
        """
        url_path = str(request.url.path)
        # URL format: /v1/blueprints/{blueprint}/entities/{identifier}
        parts = [p for p in url_path.strip("/").split("/") if p]

        if len(parts) >= 5 and parts[0] == "v1" and parts[1] == "blueprints":
            blueprint = parts[2]
            identifier = parts[4]  # parts[3] is "entities"

            # URL decode the identifier (it's encoded with quote_plus)
            identifier = unquote_plus(identifier)

            deleted_entity = {
                "identifier": identifier,
                "blueprint": blueprint,
            }
            self.deleted_entity_ids.append(identifier)
            self.deleted_entities.append(deleted_entity)

        return {"json": {"ok": True}}

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
