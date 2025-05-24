import asyncio
import inspect
from collections import defaultdict
from typing import Any, Dict, List, Optional, Type
from loguru import logger

from client.github import GitHubClient
from .base import HookHandler

EventConfig = Dict[str, Any]

class BaseEventHandler:
    """Base event handler with observer pattern implementation."""
    
    def __init__(self) -> None:
        self._observers: Dict[str, List[Any]] = defaultdict(list)

    def subscribe(self, event: str, observer: Any) -> None:
        """Subscribe an observer to an event."""
        self._observers[event].append(observer)

    async def notify(self, event: str, body: Dict[str, Any]) -> None:
        """Notify all observers of an event with parallel processing."""
        observers = self._observers.get(event, [])
        if not observers:
            return

        tasks = []
        for observer in observers:
            if asyncio.iscoroutinefunction(observer):
                if inspect.ismethod(observer):
                    handler = observer.__self__.__class__.__name__
                    logger.debug(
                        f"Creating task for observer: {handler}, event: {event}",
                        event=event,
                        handler=handler,
                    )
                tasks.append(observer(event, body))

        if tasks:
            results = await asyncio.gather(*tasks, return_exceptions=True)
            errors = [r for r in results if isinstance(r, Exception)]
            if errors:
                logger.error(f"Errors in handlers for {event}: {errors}")

class GitHubEventHandler(BaseEventHandler):
    """GitHub webhook event handler with improved error handling and configuration."""
    
    def __init__(self, config: Optional[EventConfig] = None) -> None:
        super().__init__()
        self._hook_handlers: Dict[str, List[Type[HookHandler]]] = defaultdict(list)
        self._clients: List[GitHubClient] = []
        self.config = config or {}
        self._setup_from_config()

    def _setup_from_config(self) -> None:
        """Configure handler based on provided configuration."""
        handlers_config = self.config.get("handlers", {})
        for event_type, handler_config in handlers_config.items():
            if handler_class := handler_config.get("handler_class"):
                self.on(handler_class)

    def on(self, hook_handler: Type[HookHandler]) -> None:
        """Register a hook handler for specific GitHub events."""
        for github_event in hook_handler.github_events:
            if self._validate_event_type(github_event):
                self._hook_handlers[github_event].append(hook_handler)

    def _validate_event_type(self, event: str) -> bool:
        """Validate if an event type is supported."""
        from webhook_handler import WebhookHandler
        if event not in WebhookHandler.SUPPORTED_EVENTS:
            logger.warning(f"Unsupported event type: {event}")
            return False
        return True

    def add_client(self, client: GitHubClient) -> None:
        """Add a GitHub client instance."""
        self._clients.append(client)

    async def handle_webhook(self, event: str, body: Dict[str, Any]) -> None:
        """Handle an incoming webhook event with parallel processing and retries.
        
        Args:
            event: The GitHub event type from x-github-event header
            body: The webhook payload
        """
        if not event:
            logger.warning("No event type provided in webhook")
            return

        handlers = self._hook_handlers.get(event, [])
        if not handlers:
            logger.warning(f"No handlers registered for event: {event}")
            return

        tasks = []
        for handler_class in handlers:
            try:
                client = self._get_client()
                if not client:
                    raise ValueError("No GitHub client configured")
                    
                handler = handler_class(client)
                tasks.append(handler.handle_with_retry(event, body))
            except Exception as e:
                logger.error(f"Error creating handler {handler_class.__name__}: {e}")

        if tasks:
            results = await asyncio.gather(*tasks, return_exceptions=True)
            errors = [r for r in results if isinstance(r, Exception)]
            if errors:
                logger.error(f"Errors in handlers for {event}: {errors}")
                raise Exception(f"Handler errors: {errors}")

    def _get_client(self) -> Optional[GitHubClient]:
        """Get a GitHub client instance if available."""
        return self._clients[0] if self._clients else None
