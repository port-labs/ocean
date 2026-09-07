from linear.client import LinearClient
from linear.client.graphql import GraphqlClient


class LinearExporter:
    def __init__(self, client: LinearClient) -> None:
        self._client = client

    @property
    def graphql(self) -> GraphqlClient:
        return self._client.graphql
