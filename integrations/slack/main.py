"""
Slack integration for Port using the Ocean framework.
This integration syncs Slack channels and users to Port.
"""
from typing import Any, Dict, List, Literal
from pydantic.fields import Field
from loguru import logger

from port_ocean.core.handlers.port_app_config.api import APIPortAppConfig
from port_ocean.core.handlers.port_app_config.models import (
    PortAppConfig,
    ResourceConfig,
    Selector
)
from port_ocean.core.integrations.base import BaseIntegration
from port_ocean.core.integrations.mixins import SyncRawMixin, SyncMixin
from port_ocean.core.event_listener.webhooks_only import WebhooksOnlyEventListener
from port_ocean.core.event_listener.base import EventListenerEvents
from port_ocean.context.ocean import PortOceanContext

class SlackSelector(Selector):
    """Selector configuration for Slack resources."""
    pass

class SlackResourceConfig(ResourceConfig):
    """Resource configuration for Slack entities."""
    kind: Literal["channel", "user", "channel_member"]
    selector: SlackSelector

class SlackPortAppConfig(PortAppConfig):
    """Application configuration for Slack integration."""
    resources: list[SlackResourceConfig | ResourceConfig] = Field(default_factory=list)

class SlackIntegration(BaseIntegration, SyncRawMixin):
    """Integration implementation for Slack."""

    class AppConfigHandlerClass(APIPortAppConfig):
        CONFIG_CLASS = SlackPortAppConfig

    class EventListenerClass(WebhooksOnlyEventListener):
        """Event listener for Slack webhooks."""
        def __init__(self, events: EventListenerEvents, event_listener_config: Any, integration: Any):
            super().__init__(events, event_listener_config)
            self._integration = integration

        # List of supported event types
        SUPPORTED_EVENTS = {
            'channel_events': [
                'channel_created',
                'channel_deleted',
                'channel_rename',
                'channel_archive',
                'channel_unarchive'
            ],
            'user_events': [
                'team_join',
                'user_change'
            ],
            'membership_events': [
                'member_joined_channel',
                'member_left_channel'
            ]
        }

        async def handle_request(self, request):
            """Handle incoming Slack events.

            This endpoint handles the following Slack Events API events:
            - channel_created: When a new channel is created
            - channel_deleted: When a channel is deleted
            - channel_rename: When a channel is renamed
            - channel_archive: When a channel is archived
            - channel_unarchive: When a channel is unarchived
            - member_joined_channel: When a user joins a channel
            - member_left_channel: When a user leaves a channel
            - user_change: When a user's data changes
            - team_join: When a new user joins the workspace

            It also handles the initial URL verification challenge from Slack.
            """
            try:
                event_data = await request.json()
                logger.debug(f"Received Slack event: {event_data}")

                # Handle Slack Events API URL verification
                if event_data.get("type") == "url_verification":
                    logger.info("Handling Slack URL verification challenge")
                    challenge = event_data.get("challenge")
                    if not challenge:
                        logger.error("Missing challenge in URL verification request")
                        raise ValueError("Missing challenge in URL verification request")
                    return {"challenge": challenge}

                # Validate event data structure
                if "event" not in event_data:
                    logger.error("Invalid event data: missing 'event' field")
                    raise ValueError("Invalid event data: missing 'event' field")

                # Handle actual events
                event = event_data["event"]
                event_type = event.get("type")

                if not event_type:
                    logger.error("Invalid event data: missing 'type' field")
                    raise ValueError("Invalid event data: missing 'type' field")

                logger.info(f"Processing Slack event type: {event_type}")

                # Process channel-related events
                if event_type in self.SUPPORTED_EVENTS['channel_events']:
                    logger.info(f"Processing channel event: {event_type}")
                    await self._integration.sync_raw_resource("channel")

                # Process user-related events
                elif event_type in self.SUPPORTED_EVENTS['user_events']:
                    logger.info(f"Processing user event: {event_type}")
                    await self._integration.sync_raw_resource("user")

                # Process membership events
                elif event_type in self.SUPPORTED_EVENTS['membership_events']:
                    channel_id = event.get("channel")
                    if not channel_id:
                        logger.error(f"Missing channel ID in {event_type} event")
                        raise ValueError(f"Missing channel ID in {event_type} event")

                    logger.info(f"Processing membership event: {event_type} for channel {channel_id}")
                    await self._integration.sync_channel_members(channel_id)

                # Handle unsupported events
                else:
                    logger.debug(f"Ignoring unsupported event type: {event_type}")

                return {"ok": True}

            except ValueError as ve:
                logger.error(f"Validation error processing Slack event: {str(ve)}")
                raise
            except Exception as e:
                logger.error(f"Error processing Slack event: {str(e)}")
                raise

    def __init__(self, context: PortOceanContext):
        """Initialize the Slack integration."""
        super().__init__(context)
        super(SyncRawMixin, self).__init__()
        self.client = None

    async def initialize(self) -> None:
        """Initialize the integration and set up the Slack client."""
        await super().initialize()

        # Initialize Slack client
        from .client import SlackApiClient
        token = self.context.config.integration.config.get("token")
        if not token:
            raise ValueError("Slack API token is required")
        self.client = SlackApiClient(token)
        logger.info("Slack client initialized successfully")

    async def initialize_client(self) -> None:
        """Initialize the Slack API client if not already initialized."""
        if not self.client:
            await self.initialize()

    async def sync_channel_members(self, channel_id: str):
        """Sync members for a specific channel."""
        await self.initialize_client()

        # Collect all members using the async generator
        members = []
        async for page in self.client.get_channel_members(channel_id):
            members.extend(page.get("members", []))

        # Update Port with channel membership data
        for member_id in members:
            await self.sync_entity_raw(
                kind="channel_member",
                raw={
                    "channel_id": channel_id,
                    "user_id": member_id
                }
            )

    async def sync_raw_resource(self, resource_type: str):
        """Sync a specific resource type (channel or user)."""
        try:
            await self.initialize_client()
            logger.info(f"Starting sync for resource type: {resource_type}")

            if resource_type == "channel":
                # Collect all channels using the async generator
                channels = []
                async for page in self.client.list_channels():
                    channels.extend(page.get("channels", []))

                # Process collected channels
                for channel in channels:
                    try:
                        await self.sync_entity_raw(
                            kind="channel",
                            raw=channel
                        )
                    except Exception as e:
                        logger.error(f"Error syncing channel {channel.get('name')}: {str(e)}")

            elif resource_type == "user":
                # Collect all users using the async generator
                users = []
                async for page in self.client.list_users():
                    users.extend(page.get("members", []))

                # Process collected users
                for user in users:
                    try:
                        await self.sync_entity_raw(
                            kind="user",
                            raw=user
                        )
                    except Exception as e:
                        logger.error(f"Error syncing user {user.get('name')}: {str(e)}")

            logger.info(f"Completed sync for resource type: {resource_type}")
        except Exception as e:
            logger.error(f"Error in sync_raw_resource for {resource_type}: {str(e)}")
            raise

    async def on_start(self):
        """Initialize the integration and perform initial data sync."""
        await self.initialize_client()

        # Sync all channels and users
        await self.sync_raw_resource("channel")
        await self.sync_raw_resource("user")

    async def on_resync(self):
        """Handle manual or scheduled resync events."""
        # Resync is same as initial sync for Slack
        await self.on_start()
