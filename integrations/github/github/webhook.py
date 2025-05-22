import hashlib
import hmac
import json
import logging
import os
import typing as t
from fastapi import Request

from .errors import (
    WebhookSignatureError,
    MissingHeaderError,
)

logger = logging.getLogger(__name__)


class WebhookHandler:
    def __init__(self, secret: str):
        if not secret:
            raise ValueError("Webhook secret cannot be empty.")
        self.secret = secret.encode("utf-8")

    @staticmethod
    def from_env(key: str = "GITHUB_WEBHOOK_SECRET") -> "WebhookHandler":
        secret = os.getenv(key)
        if not secret:
            raise ValueError(f"{key} is not set.")
        return WebhookHandler(secret)

    async def _verify_signature(self, request: Request) -> None:
        """
        Verifies the signature of the incoming GitHub webhook request.
        """
        signature_header = request.headers.get("x-hub-signature-256")
        if not signature_header:
            logger.error("Missing X-Hub-Signature-256 header. Cannot verify webhook.")
            raise MissingHeaderError("Missing X-Hub-Signature-256 header.")

        # The signature is of the form sha256=xxxx
        try:
            signature_type, signature_hash = signature_header.split("=", 1)
        except ValueError:
            logger.error(f"Malformed X-Hub-Signature-256 header: {signature_header}")
            raise WebhookSignatureError("Malformed X-Hub-Signature-256 header.")

        if signature_type.lower() != "sha256":
            logger.error(
                f"Unsupported signature type: {signature_type}. Expected sha256."
            )
            raise WebhookSignatureError(
                f"Unsupported signature type: {signature_type}."
            )

        request_body = await request.body()

        mac = hmac.new(self.secret, msg=request_body, digestmod=hashlib.sha256)
        expected_signature = mac.hexdigest()

        if not hmac.compare_digest(expected_signature, signature_hash):
            logger.error(
                f"Invalid webhook signature. Expected: {expected_signature}, Got: {signature_hash}"
            )
            raise WebhookSignatureError("Invalid webhook signature.")

        logger.info("Webhook signature verified successfully.")

    async def _handle_issues_event(self, payload: dict[str, t.Any]) -> None:
        action = payload.get("action")
        issue_data = payload.get("issue", {})
        issue_number = issue_data.get("number")
        issue_title = issue_data.get("title")
        repository_name = payload.get("repository", {}).get("full_name", "N/A")
        sender_login = payload.get("sender", {}).get("login", "N/A")

        logger.info(
            f"GitHub Event: 'issues', Action: '{action}', Repo: '{repository_name}', "
            f"Issue #{issue_number}: '{issue_title}', Sender: '{sender_login}'"
        )

    async def _handle_push_event(self, payload: dict[str, t.Any]) -> None:
        repo_name = payload.get("repository", {}).get("full_name", "N/A")
        pusher_name = payload.get("pusher", {}).get("name", "N/A")
        ref = payload.get("ref", "N/A")
        commits_count = len(payload.get("commits", []))

        logger.info(
            f"GitHub Event: 'push', Repo: '{repo_name}', Ref: '{ref}', "
            f"Pusher: '{pusher_name}', Commits: {commits_count}"
        )

    async def _handle_pull_request_event(self, payload: dict[str, t.Any]) -> None:
        action = payload.get("action")
        pr_data = payload.get("pull_request", {})
        pr_number = pr_data.get("number")
        pr_title = pr_data.get("title")
        pr_state = pr_data.get("state")
        repository_name = payload.get("repository", {}).get("full_name", "N/A")
        sender_login = payload.get("sender", {}).get("login", "N/A")

        logger.info(
            f"GitHub Event: 'pull_request', Action: '{action}', Repo: '{repository_name}', "
            f"PR #{pr_number} ('{pr_title}'), State: '{pr_state}', Sender: '{sender_login}'"
        )

    async def handle_webhook(self, request: Request) -> tuple[dict[str, t.Any], int]:
        """
        Main handler for incoming GitHub webhook requests.
        Verifies the signature and dispatches to the appropriate event handler.
        """
        try:
            await self._verify_signature(request)
        except MissingHeaderError as e:
            logger.warning(f"Webhook verification failed: {e}")
            return {"ok": False, "error": str(e)}, 400
        except WebhookSignatureError as e:
            logger.warning(f"Webhook verification failed: {e}")
            return {"ok": False, "error": str(e)}, 403
        except Exception as e:
            logger.exception("Unexpected error during webhook signature verification.")
            return {
                "ok": False,
                "error": "Internal server error during signature verification.",
            }, 500

        try:
            # Parse JSON after signature verification, as the raw body was needed for HMAC
            payload = await request.json()
        except json.JSONDecodeError as e:
            logger.error(f"Failed to decode JSON payload: {e}")
            return {"ok": False, "error": "Invalid JSON payload."}, 400
        except Exception as e:
            logger.exception("Error processing request payload.")
            return {"ok": False, "error": "Error processing payload."}, 500

        event_type = request.headers.get("x-github-event")
        delivery_id = request.headers.get("x-github-delivery", "N/A")

        logger.info(
            f"Received GitHub webhook. Event: '{event_type}', Delivery ID: '{delivery_id}'"
        )

        if not event_type:
            logger.warning("Missing X-GitHub-Event header.")
            return {"ok": False, "error": "Missing X-GitHub-Event header."}, 400

        try:
            if event_type == "issues":
                await self._handle_issues_event(payload)
            elif event_type == "push":
                await self._handle_push_event(payload)
            elif event_type == "pull_request":
                await self._handle_pull_request_event(payload)
            elif event_type == "ping":
                # GitHub sends a ping event when a webhook is first set up
                logger.info("Received 'ping' event. Webhook configured successfully.")
            else:
                logger.warning(
                    f"Unhandled event type: '{event_type}'. Delivery ID: '{delivery_id}'"
                )
                return {
                    "ok": True,
                    "message": f"Event type '{event_type}' received but not handled.",
                }, 200

            return {
                "ok": True,
                "message": f"Event '{event_type}' processed successfully.",
            }, 200

        except Exception as e:
            logger.exception(
                f"Webhook event handling failed for event '{event_type}', Delivery ID: '{delivery_id}'."
            )
            return {
                "ok": False,
                "error": f"An error occurred while processing event: {str(e)}",
            }, 500
