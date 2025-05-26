from typing import Dict, Any, Optional, Set
from fastapi import Request, HTTPException
from loguru import logger

from events.event_handler import GitHubEventHandler, EventConfig
from events.handlers.issues import IssueHandler
from events.handlers.pull_request import PullRequestHandler
from events.handlers.teams import TeamHandler
from events.handlers.workflows import WorkflowHandler
from events.handlers.repository import RepositoryEventHandler
from client.github import GitHubClient

class WebhookHandler:
    # All supported GitHub event types
    SUPPORTED_EVENTS: Set[str] = {
        # Repository events
        "repository", "repository_import", "repository_vulnerability_alert",
        "star", "fork",
        # Team events
        "team", "team_add", "membership",
        # Workflow events
        "workflow_run", "workflow_dispatch", "workflow_job",
        # Issue events
        "issues", "issue_comment",
        # Pull request events
        "pull_request", "pull_request_review", "pull_request_review_comment"
    }

    def __init__(self, config: Optional[EventConfig] = None):
        """Initialize the webhook handler with optional configuration.
        
        Args:
            config: Optional configuration for event handling
        """
        self.event_handler = GitHubEventHandler(config)
        self.github_client: Optional[GitHubClient] = None
        self._setup_handlers()

    def _setup_handlers(self) -> None:
        """Register all available event handlers."""
        # Register core handlers
        self.event_handler.on(IssueHandler)
        self.event_handler.on(PullRequestHandler)
        self.event_handler.on(TeamHandler)
        self.event_handler.on(WorkflowHandler)
        self.event_handler.on(RepositoryEventHandler)

    def configure_client(self, client: GitHubClient) -> None:
        """Configure the GitHub client for resource operations.
        
        Args:
            client: Configured GitHub client instance
        """
        self.github_client = client
        self.event_handler.add_client(client)

    async def _validate_webhook(self, request: Request) -> None:
        """Validate incoming webhook request.
        
        Args:
            request: The incoming webhook request
            
        Raises:
            HTTPException: If validation fails
        """
        if "x-github-event" not in request.headers:
            raise HTTPException(status_code=400, detail="Missing x-github-event header")
        
        if "x-hub-signature-256" not in request.headers:
            raise HTTPException(status_code=400, detail="Missing x-hub-signature-256 header")

    async def _process_webhook(self, event: str, payload: Dict[str, Any], raw_body: bytes, signature: Optional[str]) -> None:
        """Process a validated webhook.
        
        Args:
            event: GitHub event type
            payload: Webhook payload
            raw_body: Raw request body for signature verification
            signature: X-Hub-Signature-256 header value
            
        Raises:
            Exception: If processing fails
        """
        if not self.github_client:
            logger.warning("No GitHub client configured, some features may be limited")

        await self.event_handler.handle_webhook(event, payload, raw_body, signature)

    async def handle(self, request: Request) -> Dict[str, Any]:
        """Handle an incoming webhook request.
        
        Args:
            request: The incoming webhook request
            
        Returns:
            Response indicating success or failure
            
        Raises:
            HTTPException: For invalid requests
        """
        try:
            await self._validate_webhook(request)
            
            # Get raw body for signature verification
            raw_body = await request.body()
            # Get signature from header
            signature = request.headers.get("x-hub-signature-256")
            
            # Parse JSON after getting raw body
            payload = await request.json()
            event = request.headers["x-github-event"]
            
            logger.info(f"Processing GitHub event: {event}")
            await self._process_webhook(event, payload, raw_body, signature)
            
            return {"ok": True, "event": event}

        except HTTPException as e:
            logger.error(f"Webhook validation failed: {e.detail}")
            raise

        except Exception as e:
            error_msg = f"Webhook processing failed: {str(e)}"
            logger.exception(error_msg)
            raise HTTPException(status_code=500, detail=error_msg)
