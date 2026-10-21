from typing import TYPE_CHECKING, Any

from loguru import logger
from pydantic.v1 import BaseModel
from port_ocean.core.ocean_types import ASYNC_GENERATOR_RESYNC_TYPE

from linear.client.constants import MAX_LABEL_CHILDREN, PAGE_SIZE, LinearObject
from linear.core.exceptions import LinearApiError
from linear.core.exporters.base_exporter import (
    GetOptions,
    PaginatedExporter,
    SingleResourceExporter,
)

if TYPE_CHECKING:
    from integration import LabelResourceConfig


class LabelListOptions(BaseModel):
    include_label_children: bool = False

    @classmethod
    def from_resource_config(
        cls, resource_config: "LabelResourceConfig"
    ) -> "LabelListOptions":
        return cls(
            include_label_children=resource_config.selector.include_label_children
        )


class GetLabelOptions(GetOptions["LabelResourceConfig"]):
    include_label_children: bool = False

    @classmethod
    def from_resource_config(
        cls, resource_config: "LabelResourceConfig", *, resource_id: str
    ) -> "GetLabelOptions":
        return cls(
            resource_id=resource_id,
            include_label_children=resource_config.selector.include_label_children,
        )


class LabelExporter(PaginatedExporter, SingleResourceExporter[GetLabelOptions]):
    object_type = LinearObject.LABELS

    async def get_paginated_resources(
        self, options: LabelListOptions | None = None
    ) -> ASYNC_GENERATOR_RESYNC_TYPE:
        include_label_children = bool(options and options.include_label_children)
        async for batch in super().get_paginated_resources(None):
            if include_label_children:
                for label in batch:
                    await self._append_remaining_label_children(label)
            yield batch

    async def get_resource(self, options: GetLabelOptions) -> dict[str, Any]:
        label = await super().get_resource(options)
        if options.include_label_children:
            await self._append_remaining_label_children(label)
        return label

    async def _append_remaining_label_children(self, label: dict[str, Any]) -> None:
        """Follow the children connection past the inline page, up to the ceiling."""
        self._drop_excess_label_children(label)
        previous_cursor: str | None = None
        while self._label_children_need_more(label):
            end_cursor: str | None = label["children"]["pageInfo"]["endCursor"]
            self._require_advancing_cursor(end_cursor, previous_cursor)
            next_page = await self._fetch_label_children_page(label["id"], end_cursor)
            if not self._merge_label_children_page(label, next_page):
                return
            previous_cursor = end_cursor

    def _drop_excess_label_children(self, label: dict[str, Any]) -> None:
        edges = label["children"]["edges"]
        if len(edges) <= MAX_LABEL_CHILDREN:
            return
        del edges[MAX_LABEL_CHILDREN:]
        self._stop_label_children(label, label["children"]["pageInfo"].get("endCursor"))

    def _label_children_need_more(self, label: dict[str, Any]) -> bool:
        """Tell whether another children page fits under the ceiling."""
        page_info = label["children"]["pageInfo"]
        if not page_info["hasNextPage"]:
            return False
        if len(label["children"]["edges"]) < MAX_LABEL_CHILDREN:
            return True
        self._stop_label_children(label, page_info.get("endCursor"))
        return False

    def _stop_label_children(
        self, label: dict[str, Any], end_cursor: str | None
    ) -> None:
        label["children"]["pageInfo"] = {
            "hasNextPage": False,
            "endCursor": end_cursor,
        }
        logger.warning(
            f"Linear label {label['id']} children truncated at "
            f"{MAX_LABEL_CHILDREN} nodes"
        )

    def _require_advancing_cursor(
        self,
        end_cursor: str | None,
        previous_cursor: str | None,
    ) -> None:
        if not end_cursor or end_cursor == previous_cursor:
            raise LinearApiError("Linear label children pagination did not advance")

    async def _fetch_label_children_page(
        self, label_id: str, after_cursor: str | None
    ) -> dict[str, Any]:
        data = await self.graphql.execute_query_template(
            "GET_LABEL_CHILDREN_PAGE",
            label_id=label_id,
            page_size=PAGE_SIZE,
            after_cursor=f', after: "{after_cursor}"',
        )
        children: dict[str, Any] = data["issueLabel"]["children"]
        if not children["edges"] and children["pageInfo"]["hasNextPage"]:
            raise LinearApiError("Linear label children pagination did not advance")
        return children

    def _merge_label_children_page(
        self, label: dict[str, Any], next_page: dict[str, Any]
    ) -> bool:
        """Merge one page into the label; tell whether another page may follow."""
        children = label["children"]
        edges = children["edges"]
        next_edges = next_page["edges"]
        if not next_edges:
            children["pageInfo"] = next_page["pageInfo"]
            return False
        remaining = MAX_LABEL_CHILDREN - len(edges)
        if len(next_edges) > remaining:
            edges.extend(next_edges[:remaining])
            self._stop_label_children(label, next_page["pageInfo"].get("endCursor"))
            return False
        edges.extend(next_edges)
        children["pageInfo"] = next_page["pageInfo"]
        return True
