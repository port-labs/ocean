from linear.client.constants import LINEAR_GRAPHQL_URL
from linear.client.graphql import GraphqlClient
from linear.client.rate_limiter import LinearRateLimitStatus
from port_ocean.context.ocean import ocean
from port_ocean.helpers.async_client import OceanAsyncClient


class LinearClient:
    def __init__(self, linear_api_key: str) -> None:
        self._linear_api_key = linear_api_key
        self._http_client = OceanAsyncClient(timeout=ocean.config.client_timeout)
        self.graphql = GraphqlClient(
            self._http_client,
            LINEAR_GRAPHQL_URL,
            auth_headers={"Authorization": self._linear_api_key},
        )

    def get_rate_limit_status(self) -> LinearRateLimitStatus | None:
        return self.graphql.get_rate_limit_status()

    @classmethod
    def create_from_ocean_configuration(cls) -> "LinearClient":
        return cls(ocean.integration_config["linear_api_key"])
