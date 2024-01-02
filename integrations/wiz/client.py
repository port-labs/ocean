from datetime import datetime, timedelta
from enum import StrEnum
from typing import Any, AsyncGenerator

import httpx
from loguru import logger
from pydantic import BaseModel, Field, PrivateAttr

from port_ocean.context.event import event
from port_ocean.utils import http_async_client, get_time

PAGE_SIZE = 50
AUTH0_URLS = ["https://auth.wiz.io/oauth/token", "https://auth0.gov.wiz.io/oauth/token"]
COGNITO_URLS = [
    "https://auth.app.wiz.io/oauth/token",
    "https://auth.gov.wiz.io/oauth/token",
]

ISSUES_GQL = """
query IssuesTable(
  $filterBy: IssueFilters
  $first: Int
  $after: String
  $orderBy: IssueOrder
) {
  issues: issuesV2(
    filterBy: $filterBy
    first: $first
    after: $after
    orderBy: $orderBy
  ) {
    nodes {
      id
      sourceRule {
        __typename
        ... on Control {
          id
          name
          controlDescription: description
          resolutionRecommendation
          securitySubCategories {
            title
            category {
              name
              framework {
                name
              }
            }
          }
        }
        ... on CloudEventRule {
          id
          name
          cloudEventRuleDescription: description
          sourceType
          type
        }
        ... on CloudConfigurationRule {
          id
          name
          cloudConfigurationRuleDescription: description
          remediationInstructions
          serviceType
        }
      }
      createdAt
      updatedAt
      dueAt
      type
      resolvedAt
      statusChangedAt
      projects {
        id
        name
        slug
        businessUnit
        riskProfile {
          businessImpact
        }
      }
      status
      severity
      entitySnapshot {
        id
        type
        nativeType
        name
        status
        cloudPlatform
        cloudProviderURL
        providerId
        region
        resourceGroupExternalId
        subscriptionExternalId
        subscriptionName
        subscriptionTags
        tags
        createdAt
        externalId
      }
      serviceTickets {
        externalId
        name
        url
      }
      notes {
        createdAt
        updatedAt
        text
        user {
          name
          email
        }
        serviceAccount {
          name
        }
      }
    }
    pageInfo {
      hasNextPage
      endCursor
    }
  }
}
"""


class TokenResponse(BaseModel):
    access_token: str = Field(alias="access_token")
    expires_in: int = Field(alias="expires_in")
    token_type: str = Field(alias="token_type")
    _retrieved_time: int = PrivateAttr(get_time())

    @property
    def expired(self) -> bool:
        return self._retrieved_time + self.expires_in < get_time()

    @property
    def full_token(self) -> str:
        return f"{self.token_type} {self.access_token}"


class CacheKeys(StrEnum):
    ISSUES = "wiz_issues"


class WizClient:
    def __init__(
        self, api_url: str, client_id: str, client_secret: str, token_url: str
    ):
        self.api_url = api_url
        self.client_id = client_id
        self.client_secret = client_secret
        self.token_url = token_url
        self.last_token_object: TokenResponse | None = None

        self.http_client = http_async_client

    @property
    async def api_auth_headers(self) -> dict[str, Any]:
        token = self._get_token()

        return {
            "Authorization": token.full_token,
            "Content-Type": "application/json",
        }

    @property
    def auth_params(self) -> dict[str, Any]:
        audience_mapping = {
            **{url: "beyond-api" for url in AUTH0_URLS},
            **{url: "wiz-api" for url in COGNITO_URLS},
        }

        if self.token_url not in audience_mapping:
            raise Exception("Invalid Token URL")

        audience = audience_mapping[self.token_url]

        return {
            "grant_type": "client_credentials",
            "audience": audience,
            "client_id": self.client_id,
            "client_secret": self.client_secret,
        }

    def _get_token(self) -> TokenResponse:
        try:
            response = httpx.post(
                self.token_url,
                data=self.auth_params,
                headers={"Content-Type": "application/x-www-form-urlencoded"},
            )
            response.raise_for_status()
            return TokenResponse(**response.json())
        except Exception as e:
            logger.exception(e)
            raise

    @property
    async def token(self) -> str:
        if not self.last_token_object or not self.last_token_object.is_valid:
            msg = "Wiz Token expired or invalid, fetching new token"
            logger.info(msg)
            self.last_token_object = await self._get_token(
                self.client_id, self.client_secret
            )

        return self.last_token_object.token

    async def get_issues(self) -> AsyncGenerator[list[dict[str, Any]], None]:
        logger.info("Fetching issues from Wiz API")

        if cache := event.attributes.get(CacheKeys.ISSUES):
            logger.info("picking Wiz issues from cache")
            yield cache

        json_data: dict[str, Any] = {
            "query": ISSUES_GQL,
            "variables": {
                "first": PAGE_SIZE,
                "orderBy": {"direction": "DESC", "field": "CREATED_AT"},
            },
        }

        try:
            response = await self.http_client.post(
                url=self.api_url,
                json=json_data,
                headers=await self.api_auth_headers,
            )
            response.raise_for_status()
            response_json = response.json()
            data = response_json.get("data")

            if not data:
                logger.error(response_json.get("error"))
                raise Exception("No data found for Wiz account")

            issues = data["issues"]["nodes"]
            event.attributes[CacheKeys.ISSUES] = issues
            yield issues

        except httpx.HTTPError as e:
            logger.error(f"Error while fetching issues: {str(e)}")
            raise
