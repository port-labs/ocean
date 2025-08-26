from abc import ABC, abstractmethod
from typing import Any, Dict
from loguru import logger

from port_ocean.core.handlers.webhook.base import WebhookProcessor
from port_ocean.context.ocean import ocean


class BaseCheckmarxWebhookProcessor(WebhookProcessor, ABC):
    """Base class for all Checkmarx One webhook processors."""

    def __init__(self):
        super().__init__()

    @abstractmethod
    async def _process_webhook_data(self, body: Dict[str, Any]) -> Dict[str, Any]:
        """
        Process the webhook data and return the processed entity data.
        
        Args:
            body: The webhook payload body
            
        Returns:
            Processed entity data ready for upsert
        """
        pass

    async def process_webhook_request(self, body: Dict[str, Any]) -> None:
        """
        Main webhook processing method.
        
        Args:
            body: The webhook payload body
        """
        try:
            logger.info(f"Processing {self.__class__.__name__} webhook")
            
            # Validate webhook payload
            if not self._validate_webhook_payload(body):
                logger.error(f"Invalid webhook payload for {self.__class__.__name__}")
                return
            
            # Process the webhook data
            processed_data = await self._process_webhook_data(body)
            
            if processed_data:
                logger.info(f"Successfully processed webhook data: {processed_data.get('identifier', 'unknown')}")
            else:
                logger.warning(f"No data to process from webhook")
                
        except Exception as e:
            logger.error(f"Error processing webhook in {self.__class__.__name__}: {str(e)}")
            raise

    def _validate_webhook_payload(self, body: Dict[str, Any]) -> bool:
        """
        Validate the basic webhook payload structure.
        
        Args:
            body: The webhook payload body
            
        Returns:
            True if payload is valid, False otherwise
        """
        required_fields = ["eventType", "timestamp"]
        
        for field in required_fields:
            if field not in body:
                logger.error(f"Missing required field '{field}' in webhook payload")
                return False
                
        return True

    def _extract_entity_data(self, body: Dict[str, Any], data_path: str = "data") -> Dict[str, Any]:
        """
        Extract entity data from webhook payload.
        
        Args:
            body: The webhook payload body
            data_path: Path to the entity data in the payload
            
        Returns:
            Entity data dictionary
        """
        return body.get(data_path, {})