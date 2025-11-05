import hashlib
import hmac
from typing import Optional
from loguru import logger


def validate_webhook_signature(payload: bytes, signature: str, secret: Optional[str]) -> bool:
    """Validate Harbor webhook signature."""
    if not secret:
        logger.warning("No webhook secret configured, skipping signature validation")
        return True
        
    if not signature:
        logger.error("No signature provided in webhook request")
        return False
        
    try:
        # Harbor uses SHA256 HMAC with format: sha256=<hash>
        if not signature.startswith("sha256="):
            logger.error(f"Invalid signature format: {signature}")
            return False
            
        expected_signature = signature[7:]  # Remove 'sha256=' prefix
        computed_signature = hmac.new(
            secret.encode('utf-8'),
            payload,
            hashlib.sha256
        ).hexdigest()
        
        is_valid = hmac.compare_digest(expected_signature, computed_signature)
        
        if not is_valid:
            logger.error("Webhook signature validation failed")
        else:
            logger.debug("Webhook signature validated successfully")
            
        return is_valid
        
    except Exception as e:
        logger.error(f"Error validating webhook signature: {e}")
        return False


def extract_resource_info(event_data: dict) -> dict:
    """Extract resource information from Harbor webhook event."""
    event_type = event_data.get("type", "")
    
    # Extract common resource info
    resource_info = {
        "event_type": event_type,
        "project_name": None,
        "repository_name": None,
        "artifact_digest": None,
        "tag": None
    }
    
    # Extract project info
    if "project" in event_data.get("event_data", {}):
        project = event_data["event_data"]["project"]
        resource_info["project_name"] = project.get("name")
        
    # Extract repository info
    if "repository" in event_data.get("event_data", {}):
        repository = event_data["event_data"]["repository"]
        repo_name = repository.get("name", "")
        if "/" in repo_name:
            resource_info["repository_name"] = repo_name.split("/", 1)[1]
        else:
            resource_info["repository_name"] = repo_name
            
    # Extract artifact info
    if "resources" in event_data.get("event_data", {}):
        resources = event_data["event_data"]["resources"]
        if resources and len(resources) > 0:
            resource = resources[0]
            resource_info["artifact_digest"] = resource.get("digest")
            resource_info["tag"] = resource.get("tag")
            
    return resource_info


class HarborEventType:
    # Project events
    PROJECT_QUOTA_EXCEED = "PROJECT_QUOTA_EXCEED"
    PROJECT_QUOTA_WARNING = "PROJECT_QUOTA_WARNING"
    
    # Repository events  
    PUSH_ARTIFACT = "PUSH_ARTIFACT"
    PULL_ARTIFACT = "PULL_ARTIFACT"
    DELETE_ARTIFACT = "DELETE_ARTIFACT"
    
    # Scanning events
    SCANNING_FAILED = "SCANNING_FAILED"
    SCANNING_COMPLETED = "SCANNING_COMPLETED"
    
    # Replication events
    REPLICATION = "REPLICATION"