from typing import Optional, Dict, Any, List
import json
import httpx
from loguru import logger
from newrelic_integration.utils import render_query
from newrelic_integration.core.utils import send_graph_api_request
from newrelic_integration.core.query_templates.webhooks import (
    CREATE_WORKFLOW_MUTATION,
    FIND_WORKFLOW_BY_NAME_QUERY,
    GET_ISSUE_ENTITY_GUIDS_QUERY,
    CREATE_CHANNEL_MUTATION,
    CREATE_DESTINATION_MUTATION,
    FIND_DESTINATION_BY_TYPE_AND_URL_QUERY,
)
from port_ocean.context.ocean import ocean


class NewRelicWebhookManager:
    def __init__(self, http_client: httpx.AsyncClient):
        self.http_client = http_client

    async def _webhook_destination_exists(self, base_url: str) -> Optional[str]:
        """
        Check if a webhook with the given base_url already exists in New Relic.
        Filters by URL.
        """
        account_id = int(ocean.integration_config["new_relic_account_id"])
        query = FIND_DESTINATION_BY_TYPE_AND_URL_QUERY.replace(
            "{{ account_id }}", str(account_id)
        ).replace("{{ destination_url }}", base_url)
        response = await send_graph_api_request(
            self.http_client,
            query,
            request_type="find_destination_by_url",
            account_id=account_id,
        )

        try:
            entities = response["data"]["actor"]["account"]["aiNotifications"][
                "destinations"
            ]["entities"]
        except (KeyError, TypeError):
            logger.error("Unexpected response structure from New Relic: {}", response)
            return None

        for entity in entities:
            if entity.get("type") == "WEBHOOK" and entity.get("active"):
                url_property = next(
                    (
                        prop
                        for prop in entity.get("properties", [])
                        if prop.get("key") == "url"
                    ),
                    None,
                )
                if url_property and url_property.get("value") == base_url:
                    return entity["id"]
        return None

    async def _notification_workflow_exists(
        self, workflow_name: str
    ) -> Optional[List[Dict[str, Any]]]:
        """Get existing workflows by name."""
        account_id = int(ocean.integration_config["new_relic_account_id"])
        query = await render_query(
            FIND_WORKFLOW_BY_NAME_QUERY,
            account_id=account_id,
            workflow_name=workflow_name,
        )
        response = await send_graph_api_request(
            self.http_client,
            query,
            request_type="get_existing_workflows",
            account_id=account_id,
            workflow_name=workflow_name,
        )
        data = response.get("data", {})
        workflows_data = (
            data.get("actor", {})
            .get("account", {})
            .get("aiWorkflows", {})
            .get("entities")
        )

        return workflows_data

    async def _create_webhook_destination_request(
        self, webhook_name: str, webhook_url: str
    ) -> Optional[Dict[str, Any]]:
        """Create a new webhook destination in New Relic"""
        account_id = int(ocean.integration_config["new_relic_account_id"])
        webhook_user = ocean.integration_config.get("webhook_username")
        webhook_secret = ocean.integration_config.get("webhook_secret")
        auth_config = None
        if webhook_secret and webhook_user:
            auth_config = {
                "type": "BASIC",
                "basic": {
                    "username": webhook_user,
                    "password": webhook_secret,
                },
            }
        mutation = await render_query(
            CREATE_DESTINATION_MUTATION,
            accountId=account_id,
            name=webhook_name,
            url=webhook_url,
            auth=auth_config,
        )
        response = await send_graph_api_request(
            self.http_client,
            mutation,
            request_type="create_webhook",
            account_id=account_id,
            webhook_name=webhook_name,
            webhook_url=webhook_url,
        )
        return response

    async def create_webhook_destination(
        self, webhook_name: str, webhook_url: str
    ) -> str | None:
        """Get existing webhook or create a new one if it doesn't exist."""
        webhook_id = await self._webhook_destination_exists(webhook_url)
        if webhook_id:
            logger.info("Webhook destination already exist")
            return webhook_id

        webhook_creation_result = await self._create_webhook_destination_request(
            webhook_name, webhook_url
        )
        if webhook_creation_result:
            if not webhook_creation_result.get("data"):
                logger.error(
                    "Failed to create New Relic webhook destination, request returned an empty response"
                )
                return None

            creation_data = webhook_creation_result["data"].get(
                "aiNotificationsCreateDestination"
            )
            if creation_data.get("destination"):
                webhook_id = creation_data["destination"]["id"]
                logger.success(f"Created new webhook with ID: {webhook_id}")
                return webhook_id
            elif creation_data.get("error"):
                error_info = creation_data["error"]
                logger.error(
                    f"Failed to create New Relic webhook destination: Type={error_info.get('type')}, "
                )

        return None

    async def create_new_channel(
        self, account_id: int, destination_id: str, channel_name: str
    ) -> Optional[str]:
        """Get existing channel or create a new one if it doesn't exist."""
        channel_creation_result = await self._create_channel_request(
            account_id=str(account_id),
            destination_id=destination_id,
            channel_name=channel_name,
        )
        if not channel_creation_result or not channel_creation_result.get("data"):
            logger.error("Failed to create New Relic channel: No data in response")
            return None

        creation_data = channel_creation_result["data"].get(
            "aiNotificationsCreateChannel"
        )
        if creation_data and creation_data.get("channel"):
            channel_id = creation_data["channel"]["id"]
            logger.info(
                f"Created new channel with ID: {channel_id} for webhook destination ID: {destination_id}"
            )
            return channel_id
        elif creation_data and creation_data.get("error"):
            error_info = creation_data["error"]
            logger.error(
                "Unable to create the New Relic notification channel. "
                "Error Type: '{type}', Description: '{description}', Details: '{details}'.".format(
                    type=error_info.get("type", "N/A"),
                    description=error_info.get(
                        "description", "No description provided"
                    ),
                    details=error_info.get("details", "No additional details provided"),
                )
            )
        else:
            logger.error(
                f"Failed to create New Relic channel: Unknown error: {channel_creation_result}"
            )

        return None

    async def create_notification_workflow(
        self, account_id: int, channel_id: str, workflow_name: str
    ) -> bool:
        """Get existing workflow or create a new one if it doesn't exist."""
        workflows_exist = await self._notification_workflow_exists(workflow_name)
        if workflows_exist:
            logger.info(
                f"Workflow with name '{workflow_name}' already exists with ID: {workflows_exist[0]['id']}"
            )
            return True

        workflow_creation_result = await self._create_notification_workflow_request(
            account_id=account_id, channel_id=channel_id, workflow_name=workflow_name
        )
        if not workflow_creation_result or not workflow_creation_result.get("data"):
            logger.error("Failed to create New Relic workflow: No data in response")
            return False

        creation_data = workflow_creation_result["data"].get(
            "aiWorkflowsCreateWorkflow"
        )
        if creation_data and creation_data.get("workflow"):
            workflow_id = creation_data["workflow"]["id"]
            logger.success(
                f"Created new workflow with ID: {workflow_id} for channel ID: {channel_id}"
            )
            return True
        elif creation_data and creation_data.get("error"):
            error_info = creation_data["error"]
            logger.error(
                f"Failed to create New Relic workflow: Type={error_info.get('type')}, "
                f"Description={error_info.get('description')}, Details={error_info.get('details')}"
            )
        else:
            logger.error(
                f"Failed to create New Relic workflow: Unknown error: {workflow_creation_result}"
            )

        return False

    async def create_webhook(self) -> bool:
        """Ensure the webhook, channel, and workflow exist, create them if they don't"""
        account_id = int(ocean.integration_config["new_relic_account_id"])
        webhook_name = f"Port - {account_id}"
        webhook_url = f"{ocean.app.base_url}/integration/webhook"
        channel_name = "port-webhook-channel"
        workflow_name = "port-webhook-workflow"

        webhook_id = await self.create_webhook_destination(webhook_name, webhook_url)
        if not webhook_id:
            return False

        channel_id = await self.create_new_channel(account_id, webhook_id, channel_name)
        if not channel_id:
            return False

        return await self.create_notification_workflow(
            account_id, channel_id, workflow_name
        )

    async def get_issue_entity_guids(self, issue_id: str) -> Optional[List[str]]:
        """Fetch and return the entityGuids for a given issue ID."""
        account_id = int(ocean.integration_config["new_relic_account_id"])
        query = await render_query(
            GET_ISSUE_ENTITY_GUIDS_QUERY, account_id=account_id, issue_id=issue_id
        )
        response = await send_graph_api_request(
            self.http_client,
            query,
            request_type="get_issue_entity_guids",
            account_id=account_id,
            issue_id=issue_id,
        )
        data = response.get("data", {})
        issues_data = data["actor"]["account"]["aiIssues"]["issues"]["issues"]
        if issues_data and len(issues_data) > 0:
            return issues_data[0].get("entityGuids")
        return None

    async def _create_channel_request(
        self, account_id: str, destination_id: str, channel_name: str
    ) -> Optional[Dict[str, Any]]:
        """Create a notification channel in New Relic with the specified payload template."""
        payload_template = """{
            "id": {{ json issueId }},
            "issueUrl": {{ json issuePageUrl }},
            "title": {{ json annotations.title.[0] }},
            "severity": {{ json priority }},
            "impactedEntities": {{ json entitiesData.names }},
            "totalIncidents": {{ json totalIncidents }},
            "state": {{ json state }},
            "trigger": {{ json triggerEvent }},
            "isCorrelated": {{ json isCorrelated }},
            "createdAt": {{ createdAt }},
            "updatedAt": {{ updatedAt }},
            "lastReceived": {{ updatedAt }},
            "source": {{ json accumulations.source }},
            "alertPolicyNames": {{ json accumulations.policyName }},
            "alertConditionNames": {{ json accumulations.conditionName }},
            "workflowName": {{ json workflowName }}
        }"""
        payload_value = json.dumps(payload_template)
        mutation = await render_query(
            CREATE_CHANNEL_MUTATION,
            accountId=account_id,
            channelName=channel_name,
            destinationId=destination_id,
            payloadValue=payload_value,
        )
        response = await send_graph_api_request(
            self.http_client,
            mutation,
            request_type="create_channel",
            accountId=account_id,
            channelName=channel_name,
            destinationId=destination_id,
        )
        return response

    async def _create_notification_workflow_request(
        self, account_id: int, channel_id: str, workflow_name: str
    ) -> Optional[Dict[str, Any]]:
        """Create a notification workflow in New Relic."""
        query = await render_query(
            CREATE_WORKFLOW_MUTATION,
            accountId=account_id,
            channelId=channel_id,
            workflowName=workflow_name,
        )
        response = await send_graph_api_request(
            self.http_client,
            query,
            request_type="create_workflow",
            accountId=account_id,
            channelId=channel_id,
        )
        return response
