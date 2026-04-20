from clickup.clients.http.base_client import BaseClickUpClient


class ClickUpClient(BaseClickUpClient):
    """Client for interacting with the ClickUp API.

    This client provides ONLY generic HTTP methods.
    Resource-specific logic belongs in Exporters.

    API Base URL: https://api.clickup.com/api
    API Version: v2 (primary), some endpoints use v3

    Reference: https://developer.clickup.com/docs/
    """

    pass
