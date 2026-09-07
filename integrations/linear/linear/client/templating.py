from typing import Any

import jinja2

from linear.client.graphql import GraphqlClient
from linear.queries import QUERIES


async def execute_query_template(
    graphql: GraphqlClient,
    template_key: str,
    *,
    error_prefix: str,
    **template_vars: str,
) -> dict[str, Any]:
    template = jinja2.Template(QUERIES[template_key], enable_async=True)
    query = await template.render_async(**template_vars)
    return await graphql.execute(query, error_prefix=error_prefix)
