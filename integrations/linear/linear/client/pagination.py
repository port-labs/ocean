from typing import Any, AsyncGenerator

import jinja2
from loguru import logger

from linear.client.constants import CONNECTION_KEYS, PAGE_SIZE, LinearObject
from linear.client.graphql import GraphqlClient
from linear.queries import QUERIES


async def paginate_graphql_objects(
    graphql: GraphqlClient,
    object_type: LinearObject,
    *,
    page_size: int = PAGE_SIZE,
) -> AsyncGenerator[list[dict[str, Any]], None]:
    connection_key = CONNECTION_KEYS[object_type]
    has_next_page = True
    end_cursor: str | None = None

    while has_next_page:
        template = jinja2.Template(
            QUERIES[f"GET_{object_type}_PAGE"], enable_async=True
        )
        query = await template.render_async(
            page_size=page_size,
            after_cursor=f', after: "{end_cursor}"' if end_cursor else "",
            base_query_fields=(
                QUERIES[f"BASE_{object_type}_QUERY_FIELDS"]
                if f"BASE_{object_type}_QUERY_FIELDS" in QUERIES
                else ""
            ),
        )
        logger.debug(f"{object_type} query: {query}")
        data = await graphql.execute(
            query,
            error_prefix=f"Could not paginate {connection_key}",
        )
        connection = data[connection_key]
        yield [edge["node"] for edge in connection["edges"]]
        has_next_page = connection["pageInfo"]["hasNextPage"]
        end_cursor = connection["pageInfo"]["endCursor"]
