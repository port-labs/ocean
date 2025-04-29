from typing import Optional, Dict, Any, List
import json
import httpx
from loguru import logger
from newrelic_integration.utils import render_query
from newrelic_integration.core.utils import send_graph_api_request
from newrelic_integration.core.query_templates.webhooks import (
    GET_EXISTING_CHANNEL_QUERY,
    GET_EXISTING_WEBHOOKS_QUERY,
    GET_EXISTING_WORKFLOWS_QUERY,
    GET_ISSUE_ENTITY_GUIDS_QUERY,
)
from port_ocean.context.ocean import ocean


class NewRelicWebhookManager:
    def __init__(self, http_client: httpx.AsyncClient):
        self.http_client = http_client

    async def get_existing_webhooks(self) -> list[dict[str, Any]]:
        """Get all existing webhooks in New Relic"""
        account_id = int(ocean.integration_config["new_relic_account_id"])
        query = await render_query(GET_EXISTING_WEBHOOKS_QUERY, account_id=account_id)

        response = await send_graph_api_request(
            self.http_client,
            query,
            request_type="get_existing_webhooks",
            account_id=account_id,
        )
        data = response.get("data", {})
        destinations = (
            data.get("actor", {})
            .get("account", {})
            .get("aiNotifications", {})
            .get("destinations", {})
            .get("entities", [])
        )
        webhooks = []
        for dest in destinations:
            if dest.get("type") == "WEBHOOK":
                webhook_data = {
                    "id": dest.get("id"),
                    "name": dest.get("name"),
                    "notifications": [],
                }
                url_property = next(
                    (
                        prop
                        for prop in dest.get("properties", [])
                        if prop.get("key") == "url"
                    ),
                    None,
                )
                if url_property:
                    webhook_data["notifications"].append(
                        {"baseUrl": url_property.get("value")}
                    )
                webhooks.append(webhook_data)
        return webhooks

    async def get_existing_workflows(
        self, workflow_name: str
    ) -> Optional[List[Dict[str, Any]]]:
        """Get existing workflows by name."""
        account_id = int(ocean.integration_config["new_relic_account_id"])
        query = await render_query(
            GET_EXISTING_WORKFLOWS_QUERY,
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
            .get("entities", [])
        )
        return workflows_data if workflows_data else None

    async def get_existing_channel(
        self, account_id: int, channel_name: str
    ) -> Optional[Dict[str, Any]]:
        """Get an existing channel by name."""
        query = await render_query(
            GET_EXISTING_CHANNEL_QUERY, account_id=account_id, channel_name=channel_name
        )
        response = await send_graph_api_request(
            self.http_client,
            query,
            request_type="get_existing_channel",
            account_id=account_id,
            channel_name=channel_name,
        )
        data = response.get("data", {})
        channels_data = (
            data.get("actor", {})
            .get("account", {})
            .get("aiNotifications", {})
            .get("channels", {})
            .get("entities")
        )
        if channels_data and len(channels_data) > 0:
            return channels_data[0]
        return None

    async def create_webhook(
        self, webhook_name: str, webhook_url: str
    ) -> Optional[Dict[str, Any]]:
        """Create a new webhook in New Relic"""
        account_id = int(ocean.integration_config["new_relic_account_id"])
        webhook_secret = ocean.integration_config.get("webhook_secret")

        auth_config = None
        if webhook_secret:
            auth_config = {
                "type": "BASIC",
                "basic": {
                    "username": "port",
                    "password": webhook_secret,
                },
            }

        mutation = await render_query(
            """
            mutation {
            aiNotificationsCreateDestination(
                accountId: {{ accountId }},
                destination: {
                type: WEBHOOK,
                name: "{{ name }}",
                {% if auth %}
                auth: {
                    type: BASIC,
                    basic: {
                    user: "port",
                    password: "{{ auth.basic.password }}"
                    }
                }
                {% endif %}
                properties: [
                    {
                    key: "url",
                    value: "{{ url }}"
                    }
                ]
                }
            ) {
                destination {
                id
                name
                type
                properties {
                    key
                    value
                }
                }
                error {
                ... on AiNotificationsResponseError {
                    description
                    details
                    type
                }
                }
            }
            }
            """,
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

    async def ensure_webhook_exists(self) -> bool:
        """Ensure the webhook, channel, and workflow exist, create them if they don't"""
        account_id = int(ocean.integration_config["new_relic_account_id"])
        webhook_name = f"Port - {account_id}"
        webhook_url = f"{ocean.app.base_url}/integration/webhook"
        channel_name = "port-webhook-channel"
        workflow_name = "port-webhook-workflow"

        existing_webhooks = await self.get_existing_webhooks()
        existing_webhook = next(
            (
                wh
                for wh in existing_webhooks
                if any(
                    notif.get("baseUrl") == webhook_url
                    for notif in wh.get("notifications", [])
                )
            ),
            None,
        )

        webhook_id = existing_webhook["id"] if existing_webhook else None

        if not webhook_id:
            webhook_creation_result = await self.create_webhook(
                webhook_name, webhook_url
            )
            if (
                webhook_creation_result
                and webhook_creation_result.get("data")
                and webhook_creation_result["data"].get(
                    "aiNotificationsCreateDestination"
                )
                and webhook_creation_result["data"][
                    "aiNotificationsCreateDestination"
                ].get("destination")
            ):
                webhook_id = webhook_creation_result["data"][
                    "aiNotificationsCreateDestination"
                ]["destination"]["id"]
                logger.success(f"Created new webhook with ID: {webhook_id}")
            elif (
                webhook_creation_result
                and webhook_creation_result.get("data")
                and webhook_creation_result["data"].get(
                    "aiNotificationsCreateDestination"
                )
                and webhook_creation_result["data"][
                    "aiNotificationsCreateDestination"
                ].get("error")
            ):
                error_info = webhook_creation_result["data"][
                    "aiNotificationsCreateDestination"
                ]["error"]
                logger.error(
                    f"Failed to create New Relic webhook: Type={error_info.get('type')}, Description={error_info.get('description')}, Details={error_info.get('details')}"
                )
                return False
            else:
                logger.error(
                    f"Failed to create New Relic webhook: Unknown error: {webhook_creation_result}"
                )
                return False
        else:
            logger.info(f"Webhook already exists with ID: {webhook_id}")

        channel_id = None
        if webhook_id:
            existing_channel = await self.get_existing_channel(account_id, channel_name)
            if existing_channel:
                channel_id = existing_channel["id"]
                logger.info(
                    f"Channel with name '{channel_name}' already exists with ID: {channel_id}"
                )
            else:
                channel_creation_result = await self.create_channel(
                    account_id=str(account_id),
                    destination_id=webhook_id,
                    channel_name=channel_name,
                )
                if (
                    channel_creation_result
                    and channel_creation_result.get("data")
                    and channel_creation_result["data"].get(
                        "aiNotificationsCreateChannel"
                    )
                    and channel_creation_result["data"][
                        "aiNotificationsCreateChannel"
                    ].get("channel")
                ):
                    channel_id = channel_creation_result["data"][
                        "aiNotificationsCreateChannel"
                    ]["channel"]["id"]
                    logger.success(
                        f"Created new channel with ID: {channel_id} for webhook ID: {webhook_id}"
                    )
                elif (
                    channel_creation_result
                    and channel_creation_result.get("data")
                    and channel_creation_result["data"].get(
                        "aiNotificationsCreateChannel"
                    )
                    and channel_creation_result["data"][
                        "aiNotificationsCreateChannel"
                    ].get("error")
                ):
                    error_info = channel_creation_result["data"][
                        "aiNotificationsCreateChannel"
                    ]["error"]
                    logger.error(
                        f"Failed to create New Relic channel: Type={error_info.get('type')}, Description={error_info.get('description')}, Details={error_info.get('details')}"
                    )
                    return False
                else:
                    logger.error(
                        f"Failed to create New Relic channel: Unknown error: {channel_creation_result}"
                    )
                    return False

            if channel_id:
                existing_workflows = await self.get_existing_workflows(workflow_name)
                if existing_workflows:
                    logger.info(
                        f"Workflow with name '{workflow_name}' already exists with ID: {existing_workflows[0]['id']}"
                    )
                    return True
                else:
                    workflow_creation_result = await self.create_workflow(
                        account_id=account_id,
                        channel_id=channel_id,
                        workflow_name=workflow_name,
                    )
                    if (
                        workflow_creation_result
                        and workflow_creation_result.get("data")
                        and workflow_creation_result["data"].get(
                            "aiWorkflowsCreateWorkflow"
                        )
                        and workflow_creation_result["data"][
                            "aiWorkflowsCreateWorkflow"
                        ].get("workflow")
                    ):
                        workflow_id = workflow_creation_result["data"][
                            "aiWorkflowsCreateWorkflow"
                        ]["workflow"]["id"]
                        logger.success(
                            f"Created new workflow with ID: {workflow_id} for channel ID: {channel_id}"
                        )
                        return True
                    elif (
                        workflow_creation_result
                        and workflow_creation_result.get("data")
                        and workflow_creation_result["data"].get(
                            "aiWorkflowsCreateWorkflow"
                        )
                        and workflow_creation_result["data"][
                            "aiWorkflowsCreateWorkflow"
                        ].get("error")
                    ):
                        error_info = workflow_creation_result["data"][
                            "aiWorkflowsCreateWorkflow"
                        ]["error"]
                        logger.error(
                            f"Failed to create New Relic workflow: Type={error_info.get('type')}, Description={error_info.get('description')}, Details={error_info.get('details')}"
                        )
                        return False
                    else:
                        logger.error(
                            f"Failed to create New Relic workflow: Unknown error: {workflow_creation_result}"
                        )
                        return False
            else:
                logger.warning("Channel ID is None, cannot create workflow.")
                return False

        return True

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
        issues_data = (
            data.get("actor", {})
            .get("account", {})
            .get("aiIssues", {})
            .get("issues", {})
            .get("issues", [])
        )
        if issues_data and len(issues_data) > 0:
            return issues_data[0].get("entityGuids")
        return None

    async def create_channel(
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
            """
            mutation {
              aiNotificationsCreateChannel(
                channel: {
                  product: IINT,
                  properties: {
                    key: "payload",
                    displayValue: null,
                    label: null,
                    value: {{ payloadValue }}
                  },
                  name: "{{ channelName }}",
                  destinationId: "{{ destinationId }}",
                  type: WEBHOOK
                }
                accountId: {{ accountId }}
              ) {
                channel {
                  id
                  destinationId
                }
                error {
                  ... on AiNotificationsResponseError {
                    description
                    details
                    type
                  }
                }
              }
            }
            """,
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

    async def create_workflow(
        self, account_id: int, channel_id: str, workflow_name: str
    ) -> Optional[Dict[str, Any]]:
        """Create a notification workflow in New Relic."""
        mutation = """
                mutation {
                    aiWorkflowsCreateWorkflow(
                        accountId: {{ accountId }}
                        createWorkflowData: {
                            name: "{{ workflowName }}"
                            destinationConfigurations: {
                                channelId: "{{ channelId }}"
                                notificationTriggers: [ACTIVATED, ACKNOWLEDGED, CLOSED, PRIORITY_CHANGED, INVESTIGATING, OTHER_UPDATES]
                            }
                            mutingRulesHandling: DONT_NOTIFY_FULLY_MUTED_ISSUES
                            issuesFilter: {
                                name: "team specific issues"
                                predicates: [
                                    {
                                        attribute: "accumulations.tag.team"
                                        operator: EXACTLY_MATCHES
                                        values: ["security"]
                                    }
                                ]
                                type: FILTER
                            }
                            destinationsEnabled: true
                            workflowEnabled: true
                        }
                    ) {
                        workflow {
                            id
                        }
                        errors {
                            description
                            type
                        }
                    }
                }
                """
        query = await render_query(
            mutation,
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
