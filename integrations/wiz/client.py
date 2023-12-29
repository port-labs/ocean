from datetime import datetime, timedelta
from enum import StrEnum
from typing import Any, AsyncGenerator

import httpx
from loguru import logger

from port_ocean.context.event import event
from port_ocean.utils import http_async_client

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


class CacheKeys(StrEnum):
    ISSUES = "wiz_issues"
    TOKENS = "wiz_tokens"


class WizClient:
    def __init__(
        self, api_url: str, client_id: str, client_secret: str, token_url: str
    ):
        self.api_url = api_url
        self.client_id = client_id
        self.client_secret = client_secret
        self.token_url = token_url

        self.http_client = http_async_client
        self.http_client.headers.update(self.api_auth_header)

    @property
    def api_auth_header(self) -> dict[str, Any]:
        access_token = self.get_token()

        return {
            "Authorization": f"Bearer {access_token}",
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

    def get_token(self) -> str:
        try:
            if cached_token_object := event.attributes.get(CacheKeys.TOKENS):
                if not self.is_token_expired(cached_token_object):
                    return cached_token_object["access_token"]

            response = httpx.post(
                self.token_url,
                data=self.auth_params,
                headers={"Content-Type": "application/x-www-form-urlencoded"},
            )
            response.raise_for_status()

            token_result = response.json()

            # Calculate and add expiry date to the token_result
            expiry_in_seconds = token_result.get("expires_in", 0)
            expiry_datetime = datetime.utcnow() + timedelta(seconds=expiry_in_seconds)
            token_result["expiry_date"] = expiry_datetime.isoformat()

            event.attributes[CacheKeys.TOKENS] = token_result

            return token_result["access_token"]
        except Exception as e:
            print(e)
            raise

    def is_token_expired(self, token_object: Any) -> bool:
        expiry_date_str = token_object.get("expiry_date")
        if expiry_date_str:
            expiry_date = datetime.fromisoformat(expiry_date_str)
            return expiry_date <= datetime.utcnow()
        return True

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
                headers=self.api_auth_header,
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
