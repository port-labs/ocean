from linear.client.constants import LINEAR_GRAPHQL_URL
from linear.client.graphql import GraphqlClient
from linear.client.rate_limiter import LinearRateLimitStatus
from port_ocean.context.ocean import ocean
from port_ocean.utils import http_async_client


class LinearClient:
    def __init__(self, linear_api_key: str) -> None:
        self.linear_api_key = linear_api_key
        self.api_auth_header = {"Authorization": self.linear_api_key}
        self.client = http_async_client
        self.client.headers.update(self.api_auth_header)
        self.graphql = GraphqlClient(self.client, LINEAR_GRAPHQL_URL)

    def get_rate_limit_status(self) -> LinearRateLimitStatus | None:
        return self.graphql.get_rate_limit_status()

    @classmethod
    def create_from_ocean_configuration(cls) -> "LinearClient":
        return cls(ocean.integration_config["linear_api_key"])
