from typing import Any, AsyncGenerator

from port_ocean.core.ocean_types import RAW_ITEM

from confluence.clients.client import ConfluenceClient
from confluence.core.exporters.abstract_exporter import AbstractConfluenceExporter
from confluence.core.options import PageExportOptions
from confluence.helpers.utils import attach_web_url

METADATA_PAGE_SIZE = 250
BODY_PAGE_SIZE = 25
PARENT_ENDPOINTS = {
    "page": "pages",
    "folder": "folders",
    "whiteboard": "whiteboards",
    "database": "databases",
}
# Pages come from the list call. Embed has no get-by-id, so it stays an id in the path.
FETCHED_PARENT_TYPES = {"folder", "whiteboard", "database"}


class PageExporter(AbstractConfluenceExporter[ConfluenceClient]):
    """Exports pages with a folderPath and filePath built from their ancestor titles."""

    async def get_paginated_resources(
        self, options: PageExportOptions | None = None
    ) -> AsyncGenerator[list[RAW_ITEM], None]:
        selected = options or PageExportOptions()
        pages, nodes = await self._load_hierarchy(selected)

        if selected.include_body:
            # Second pass only when bodies are needed. Streams them in small batches.
            async for batch in self.client.send_paginated_request(
                "pages", params=self._params(selected, with_body=True)
            ):
                yield [self._enrich(item, nodes) for item in batch]
        else:
            # Metadata already has everything, so reuse it instead of listing again.
            for start in range(0, len(pages), METADATA_PAGE_SIZE):
                yield [
                    self._enrich(item, nodes)
                    for item in pages[start : start + METADATA_PAGE_SIZE]
                ]

    async def get_single_resource(self, resource_id: str) -> RAW_ITEM | None:
        payload = await self.client.send_api_request(
            f"pages/{resource_id}", missing_ok=True
        )
        if not payload or not payload.get("id"):
            return None
        # Webhooks have no preloaded map, so fetch only this page's ancestors.
        nodes: dict[str, dict[str, Any]] = {}
        await self._fill_ancestors(payload, nodes)
        return self._enrich(payload, nodes)

    def _params(self, selected: PageExportOptions, with_body: bool) -> dict[str, Any]:
        params: dict[str, Any] = {
            "status": (
                ["current", "archived"] if selected.include_archived else ["current"]
            ),
        }
        if with_body:
            params["body-format"] = "markdown"
            params["limit"] = BODY_PAGE_SIZE
        else:
            params["limit"] = METADATA_PAGE_SIZE
        if selected.space_ids:
            params["space-id"] = selected.space_ids
        return params

    async def _load_hierarchy(
        self, selected: PageExportOptions
    ) -> tuple[list[dict[str, Any]], dict[str, dict[str, Any]]]:
        pages: list[dict[str, Any]] = []
        nodes: dict[str, dict[str, Any]] = {}

        async for batch in self.client.send_paginated_request(
            "pages", params=self._params(selected, with_body=False)
        ):
            for page in batch:
                pages.append(page)
                nodes[page["id"]] = _link(page)

        await self._resolve_parents(pages, nodes)
        return pages, nodes

    async def _resolve_parents(
        self, pages: list[dict[str, Any]], nodes: dict[str, dict[str, Any]]
    ) -> None:
        # Folders, whiteboards, and databases have no list endpoint here, so only
        # the ones pages sit under are fetched, once each. Embed is left as an id.
        pending = [
            (page["parentType"], page["parentId"])
            for page in pages
            if page.get("parentType") in FETCHED_PARENT_TYPES and page.get("parentId")
        ]
        while pending:
            parent_type, parent_id = pending.pop()
            if parent_id in nodes:
                continue
            payload = await self.client.send_api_request(
                f"{PARENT_ENDPOINTS[parent_type]}/{parent_id}", missing_ok=True
            )
            if not payload or not payload.get("id"):
                continue  # _enrich keeps the raw ID for this level
            nodes[parent_id] = _link(payload)
            next_type = payload.get("parentType")
            next_id = payload.get("parentId")
            if next_type in FETCHED_PARENT_TYPES and next_id:
                pending.append((next_type, next_id))

    def _enrich(
        self, item: dict[str, Any], nodes: dict[str, dict[str, Any]]
    ) -> dict[str, Any]:
        item = attach_web_url(self.client.site_url, item)
        titles: list[str] = []
        parent_id = item.get("parentId")
        seen = {item["id"]}
        while parent_id and parent_id not in seen:
            seen.add(parent_id)
            node = nodes.get(parent_id)
            if node is None:
                # Unknown level (e.g. archived parent not loaded): keep its ID.
                titles.insert(0, parent_id)
                break
            titles.insert(0, node["title"])
            parent_id = node["parentId"]

        folder_path = "/".join([_space_key(item), *titles])
        item["__folderPath"] = folder_path
        item["__filePath"] = (
            f"{folder_path}/{_safe(item.get('title') or item['id'])}.md"
        )
        return item

    async def _fill_ancestors(
        self, item: dict[str, Any], nodes: dict[str, dict[str, Any]]
    ) -> None:
        parent_id = item.get("parentId")
        parent_type = item.get("parentType")
        seen = {item["id"]}
        while parent_id and parent_id not in seen:
            seen.add(parent_id)
            if parent_id not in nodes:
                endpoint = PARENT_ENDPOINTS.get(parent_type or "")
                if not endpoint:
                    break
                payload = await self.client.send_api_request(
                    f"{endpoint}/{parent_id}", missing_ok=True
                )
                if not payload or not payload.get("id"):
                    break
                nodes[parent_id] = _link(payload)
            node = nodes[parent_id]
            parent_id = node["parentId"]
            parent_type = node["parentType"]


def _link(node: dict[str, Any]) -> dict[str, Any]:
    return {
        "title": _safe(node.get("title") or node["id"]),
        "parentId": node.get("parentId"),
        "parentType": node.get("parentType"),
    }


def _space_key(item: dict[str, Any]) -> str:
    webui = (item.get("_links") or {}).get("webui", "")
    parts = webui.split("/")
    key = parts[2] if len(parts) > 2 else item["spaceId"]
    return key.lstrip("~")


def _safe(name: str) -> str:
    return name.replace("/", "-").strip()
