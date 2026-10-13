from typing import TYPE_CHECKING, Any

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


def _reject_oversized_label_children(label_id: str, count: int) -> None:
    if count > MAX_LABEL_CHILDREN:
        raise LinearApiError(
            f"Linear label {label_id} children exceeded {MAX_LABEL_CHILDREN} nodes"
        )


class GetLabelOptions(GetOptions["LabelResourceConfig"]):
    @classmethod
    def from_resource_config(
        cls, resource_config: "LabelResourceConfig", *, resource_id: str
    ) -> "GetLabelOptions":
        return cls(resource_id=resource_id)


class LabelExporter(PaginatedExporter, SingleResourceExporter[GetLabelOptions]):
    object_type = LinearObject.LABELS

    async def get_paginated_resources(
        self, options: None = None
    ) -> ASYNC_GENERATOR_RESYNC_TYPE:
        async for batch in super().get_paginated_resources(options):
            for label in batch:
                await self._append_remaining_label_children(label)
            yield batch

    async def get_resource(self, options: GetLabelOptions) -> dict[str, Any]:
        label = await super().get_resource(options)
        await self._append_remaining_label_children(label)
        return label

    async def _append_remaining_label_children(self, label: dict[str, Any]) -> None:
        children = label["children"]
        edges = children["edges"]
        _reject_oversized_label_children(label["id"], len(edges))
        previous_cursor = None
        while children["pageInfo"]["hasNextPage"]:
            if len(edges) >= MAX_LABEL_CHILDREN:
                _reject_oversized_label_children(label["id"], len(edges) + 1)
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
            _reject_oversized_label_children(label["id"], len(edges) + len(next_edges))
            edges.extend(next_edges)
            children["pageInfo"] = next_page["pageInfo"]
            previous_cursor = end_cursor
