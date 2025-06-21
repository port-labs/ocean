from datetime import datetime, timedelta, timezone
from .base import BaseFetcher

from integrations.spacelift.utils.logger import logger
from ..config import Config

app_config = Config()


DEPLOYMENTS_QUERY = """
query Deployments($status: RunStatus, $since: Time) {
  runs(status: $status, since: $since) {
    id
    createdAt
    updatedAt
    status
    trigger
    commit
    message
    stack {
      id
      name
    }
    initiatedBy {
      id
      email
    }
  }
}
"""

SINGLE_RUN_QUERY = """
query GetRun($id: ID!) {
  run(id: $id) {
    id
    createdAt
    updatedAt
    status
    trigger
    commit
    message
    stack {
      id
      name
    }
    initiatedBy {
      id
      email
    }
  }
}
"""

class DeploymentsFetcher(BaseFetcher):
    kind = "spacelift-deployment"

    async def fetch(self):
        status = app_config.BLUEPRINT_CONFIG.get("run_status_filter", "FINISHED")
        days_back = int(app_config.BLUEPRINT_CONFIG.get("run_days_back", 7))
        since_date = (datetime.now(timezone.utc) - timedelta(days=days_back)).isoformat() + "Z"

        logger.info(f"Fetching Spacelift deployments with status={status} since={since_date}...")
        result = await self.client.query(
            DEPLOYMENTS_QUERY,
            variables={"status": status, "since": since_date},
        )

        runs = result.get("data", {}).get("runs", [])
        logger.info(f"Fetched {len(runs)} runs.")

        for run in runs:
            logger.debug(f"Yielding run: {run['id']}")
            yield self._format_run(run)

    async def fetch_by_id(self, run_id: str):
        logger.info(f"Fetching Spacelift run by ID: {run_id}")
        result = await self.client.query(
            SINGLE_RUN_QUERY,
            variables={"id": run_id},
        )

        run = result.get("data", {}).get("run")
        if run:
            logger.debug(f"Yielding webhook-triggered run: {run['id']}")
            yield self._format_run(run)
        else:
            logger.warning(f"No run found for ID {run_id}")

    @staticmethod
    def _format_run(run: dict) -> dict:
        return {
            "identifier": run["id"],
            "title": f"{run['stack']['name']} - {run['status']}",
            "properties": {
                "created_at": run.get("createdAt"),
                "updated_at": run.get("updatedAt"),
                "status": run.get("status"),
                "trigger": run.get("trigger"),
                "commit": run.get("commit"),
                "message": run.get("message"),
                "stack_id": run.get("stack", {}).get("id"),
                "stack_name": run.get("stack", {}).get("name"),
                "initiated_by_id": run.get("initiatedBy", {}).get("id"),
                "initiated_by_email": run.get("initiatedBy", {}).get("email"),
            },
        }
