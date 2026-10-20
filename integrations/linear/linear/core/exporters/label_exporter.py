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
        children = label["children"]
        edges = children["edges"]
        if len(edges) > MAX_LABEL_CHILDREN:
            del edges[MAX_LABEL_CHILDREN:]
            children["pageInfo"] = {
                "hasNextPage": False,
                "endCursor": children["pageInfo"].get("endCursor"),
            }
            logger.warning(
                f"Linear label {label['id']} children truncated at "
                f"{MAX_LABEL_CHILDREN} nodes"
            )
            return
        previous_cursor = None
        while children["pageInfo"]["hasNextPage"]:
            if len(edges) >= MAX_LABEL_CHILDREN:
                children["pageInfo"] = {
                    "hasNextPage": False,
                    "endCursor": children["pageInfo"].get("endCursor"),
                }
                logger.warning(
                    f"Linear label {label['id']} children truncated at "
                    f"{MAX_LABEL_CHILDREN} nodes"
                )
                return
            end_cursor = children["pageInfo"]["endCursor"]
            if not end_cursor or end_cursor == previous_cursor:
                raise LinearApiError("Linear label children pagination did not advance")
            data = await self.graphql.execute_query_template(
                "GET_LABEL_CHILDREN_PAGE",
                label_id=label["id"],
                page_size=PAGE_SIZE,
                after_cursor=f', after: "{end_cursor}"',
            )
            next_page = data["issueLabel"]["children"]
            next_edges = next_page["edges"]
            if not next_edges:
                if next_page["pageInfo"]["hasNextPage"]:
                    raise LinearApiError(
                        "Linear label children pagination did not advance"
                    )
                children["pageInfo"] = next_page["pageInfo"]
                return
            remaining = MAX_LABEL_CHILDREN - len(edges)
            if len(next_edges) > remaining:
                edges.extend(next_edges[:remaining])
                children["pageInfo"] = {
                    "hasNextPage": False,
                    "endCursor": next_page["pageInfo"].get("endCursor"),
                }
                logger.warning(
                    f"Linear label {label['id']} children truncated at "
                    f"{MAX_LABEL_CHILDREN} nodes"
                )
                return
            edges.extend(next_edges)
            children["pageInfo"] = next_page["pageInfo"]
            previous_cursor = end_cursor
