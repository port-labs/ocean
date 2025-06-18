import requests
from ..config import SpaceliftConfig
from ..constants import GRAPHQL_URL_TEMPLATE

def get_jwt_token(cfg: SpaceliftConfig) -> str:
    url = GRAPHQL_URL_TEMPLATE.format(account=cfg.spacelift_account)
    query = """
    mutation GetSpaceliftToken($id: ID!, $secret: String!) {
      apiKeyUser(id: $id, secret: $secret) {
        jwt
      }
    }
    """
    variables = {"id": cfg.SPACELIFT_API_KEY_ID, "secret": cfg.SPACELIFT_API_KEY_SECRET}
    response = requests.post(url, json={"query": query, "variables": variables})
    response.raise_for_status()
    return response.json()["data"]["apiKeyUser"]["jwt"]