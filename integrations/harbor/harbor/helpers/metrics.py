import time
from typing import Dict, Any, Optional
from dataclasses import dataclass, field
from loguru import logger


@dataclass
class RequestMetrics:
    """Track API request metrics."""
    method: str
    url: str
    status_code: Optional[int] = None
    latency_ms: Optional[float] = None
    retry_count: int = 0
    error: Optional[str] = None
    start_time: float = field(default_factory=time.time)
    
    def complete(self, status_code: int, error: Optional[str] = None):
        """Mark request as complete and calculate latency."""
        self.status_code = status_code
        self.latency_ms = (time.time() - self.start_time) * 1000
        self.error = error
        
    def log_request(self):
        """Log request metrics."""
        log_data = {
            "method": self.method,
            "url": self.url,
            "status_code": self.status_code,
            "latency_ms": round(self.latency_ms, 2) if self.latency_ms else None,
            "retry_count": self.retry_count
        }
        
        if self.error:
            logger.error("Harbor API request failed", **log_data, error=self.error)
        elif self.status_code and self.status_code >= 400:
            logger.warning("Harbor API request error", **log_data)
        else:
            logger.info("Harbor API request completed", **log_data)


@dataclass
class IngestionStats:
    """Track data ingestion statistics."""
    projects_processed: int = 0
    users_processed: int = 0
    repositories_processed: int = 0
    artifacts_processed: int = 0
    
    projects_skipped: int = 0
    users_skipped: int = 0
    repositories_skipped: int = 0
    artifacts_skipped: int = 0
    
    projects_errors: int = 0
    users_errors: int = 0
    repositories_errors: int = 0
    artifacts_errors: int = 0
    
    start_time: float = field(default_factory=time.time)
    
    def log_summary(self):
        """Log ingestion summary statistics."""
        duration = time.time() - self.start_time
        
        logger.info(
            "Harbor ingestion completed",
            duration_seconds=round(duration, 2),
            projects_processed=self.projects_processed,
            users_processed=self.users_processed,
            repositories_processed=self.repositories_processed,
            artifacts_processed=self.artifacts_processed,
            total_processed=self.projects_processed + self.users_processed + 
                          self.repositories_processed + self.artifacts_processed,
            projects_skipped=self.projects_skipped,
            users_skipped=self.users_skipped,
            repositories_skipped=self.repositories_skipped,
            artifacts_skipped=self.artifacts_skipped,
            total_skipped=self.projects_skipped + self.users_skipped + 
                        self.repositories_skipped + self.artifacts_skipped,
            projects_errors=self.projects_errors,
            users_errors=self.users_errors,
            repositories_errors=self.repositories_errors,
            artifacts_errors=self.artifacts_errors,
            total_errors=self.projects_errors + self.users_errors + 
                       self.repositories_errors + self.artifacts_errors
        )


class WebhookMetrics:
    """Track webhook processing metrics."""
    
    @staticmethod
    def log_webhook_received(event_type: str, project: str = None, repository: str = None):
        """Log webhook event received."""
        logger.info(
            "Harbor webhook received",
            event_type=event_type,
            project=project,
            repository=repository
        )
    
    @staticmethod
    def log_webhook_processed(event_type: str, entities_updated: int, processing_time_ms: float):
        """Log webhook processing completion."""
        logger.info(
            "Harbor webhook processed",
            event_type=event_type,
            entities_updated=entities_updated,
            processing_time_ms=round(processing_time_ms, 2)
        )
    
    @staticmethod
    def log_webhook_error(event_type: str, error: str):
        """Log webhook processing error."""
        logger.error(
            "Harbor webhook processing failed",
            event_type=event_type,
            error=error
        )
    
    @staticmethod
    def log_signature_validation(valid: bool, event_type: str = None):
        """Log webhook signature validation result."""
        if valid:
            logger.debug("Webhook signature validated", event_type=event_type)
        else:
            logger.warning("Webhook signature validation failed", event_type=event_type)