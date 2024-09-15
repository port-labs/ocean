from typing import Any
from loguru import logger

def extract_merge_request_payload(data: dict[str, Any]) -> dict[str, Any]:
    logger.info(f"Extracting merge request for project: {data['project']['id']}")
    return {
        "id": data["object_attributes"]["id"],
        "title": data["object_attributes"]["title"],
        "author": {
            "name": data["user"]["name"],
        },
        "status": data["object_attributes"]["state"],
        "createdAt": data["object_attributes"]["created_at"],
        "updatedAt": data["object_attributes"]["updated_at"],
        "link": data["object_attributes"]["source"]["web_url"],
        "reviewers": data["reviewers"][0]["name"],
        "__project": data["project"],
    }

def extract_issue_payload(data: dict[str, Any]) -> dict[str, Any]:
    logger.info(f"Extracting issue for project: {data['project']['id']}")
    return {
        "id": data["object_attributes"]["id"],
        "title": data["object_attributes"]["title"],
        "link": data["object_attributes"]["url"],
        "description": data["object_attributes"]["description"],
        "created_at": data["object_attributes"]["created_at"],
        "updated_at": data["object_attributes"]["updated_at"],
        "author": {
            "name": data["user"]["name"],
        },
        "state": data["object_attributes"]["state"],
        "labels": [label["title"] for label in data["object_attributes"]["labels"]],
        "__project": data["project"],
    }
