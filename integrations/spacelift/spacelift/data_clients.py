from typing import Any, Dict, List, AsyncGenerator, Optional

from loguru import logger

from .auth import AuthenticationError
from .base_client import SpaceliftBaseClient


class SpaceliftDataClients(SpaceliftBaseClient):
    """Data client methods for fetching different types of Spacelift resources."""

    async def get_spaces(self) -> AsyncGenerator[List[Dict[str, Any]], None]:
        """Get all spaces with pagination."""
        logger.info("Fetching Spacelift spaces")

        query = """
        query GetSpaces {
            spaces {
                id
                name
                description
                parentSpace
                labels
            }
        }
        """

        try:
            data = await self.make_graphql_request(query)
            spaces = data["data"]["spaces"] or []

            if spaces:
                yield spaces
                logger.info(f"Fetched {len(spaces)} spaces")
            else:
                yield []
                logger.info("No spaces found")

        except AuthenticationError as e:
            logger.error(
                "Authorization failed for spaces query. This may indicate insufficient permissions."
            )
            logger.error(f"Full error: {e}")
            logger.error("Please check your Spacelift API key permissions.")
            yield []

        except Exception as e:
            logger.error(f"Could not fetch spaces: {e}")
            yield []

    async def get_stacks(self) -> AsyncGenerator[List[Dict[str, Any]], None]:
        """Get all stacks with pagination."""
        logger.info("Fetching Spacelift stacks")

        query = """
        query GetStacks {
            stacks {
                id
                name
                description
                repository
                branch
                state
                administrative
                space
                labels
                provider
                terraformVersion
                projectRoot
            }
        }
        """

        try:
            data = await self.make_graphql_request(query)
            stacks = data["data"]["stacks"] or []

            if stacks:
                yield stacks
                logger.info(f"Fetched {len(stacks)} stacks")
            else:
                yield []
                logger.info("No stacks found")

        except AuthenticationError as e:
            logger.error(
                "Authorization failed for stacks query. This may indicate insufficient permissions."
            )
            logger.error(f"Full error: {e}")
            logger.error("Please check your Spacelift API key permissions.")
            yield []

        except Exception as e:
            logger.error(f"Could not fetch stacks: {e}")
            yield []

    async def get_deployments(self) -> AsyncGenerator[List[Dict[str, Any]], None]:
        """Get all deployments (tracked runs) with pagination."""
        logger.info("Fetching Spacelift deployments")

        stack_ids = []
        stack_fetch_errors = []
        
        try:
            async for stacks_batch in self.get_stacks():
                if stacks_batch:  # Only process non-empty batches
                    for stack in stacks_batch:
                        stack_ids.append(stack["id"])
                else:
                    logger.debug("Received empty stacks batch")
        except Exception as e:
            logger.error(f"Failed to fetch stacks for deployments: {e}")
            stack_fetch_errors.append(str(e))

        if not stack_ids:
            if stack_fetch_errors:
                logger.warning(f"No stacks found due to errors: {'; '.join(stack_fetch_errors)}")
            else:
                logger.info("No stacks found")
            logger.info("Yielding empty deployments list")
            yield []
            return

        logger.info(f"Fetching deployments for {len(stack_ids)} stacks")
        deployment_fetch_errors = []
        
        for stack_id in stack_ids:
            try:
                logger.debug(f"Fetching deployments for stack: {stack_id}")
                async for deployments_batch in self._get_stack_runs(
                    stack_id, run_type="TRACKED"
                ):
                    if deployments_batch:  # Only yield non-empty batches
                        yield deployments_batch
                    else:
                        logger.debug(f"No deployments found for stack: {stack_id}")
            except Exception as e:
                logger.error(f"Failed to fetch deployments for stack {stack_id}: {e}")
                deployment_fetch_errors.append(f"Stack {stack_id}: {str(e)}")
                # Continue with other stacks instead of failing completely
                continue
        
        if deployment_fetch_errors:
            logger.warning(f"Some deployment fetches failed: {'; '.join(deployment_fetch_errors)}")

    async def _get_stack_runs(
        self, stack_id: str, run_type: Optional[str] = None
    ) -> AsyncGenerator[List[Dict[str, Any]], None]:
        """Get runs for a specific stack."""
        query = """
        query GetStackRuns($stackId: ID!) {
            stack(id: $stackId) {
                id
                name
                runs {
                    id
                    type
                    state
                    branch
                    createdAt
                    updatedAt
                    triggeredBy
                    commit {
                        hash
                        message
                        authorName
                    }
                    driftDetection
                }
            }
        }
        """

        variables = {"stackId": stack_id}

        try:
            data = await self.make_graphql_request(query, variables)

            stack_data = data.get("data", {}).get("stack") if data else None
            if not stack_data:
                yield []
                return

            runs = stack_data.get("runs", []) or []
            filtered_runs = []

            for run in runs:
                if run_type and run.get("type") != run_type:
                    continue

                # Only add minimal enrichment that can't be done in JQ
                run["stack_id"] = stack_id
                run["stack"] = {
                    "id": stack_data.get("id", stack_id),
                    "name": stack_data.get("name", "Unknown"),
                }
                filtered_runs.append(run)

            yield filtered_runs

        except Exception as e:
            logger.error(f"Could not fetch runs for stack {stack_id}: {e}")
            yield []

    async def get_policies(self) -> AsyncGenerator[List[Dict[str, Any]], None]:
        """Get all policies."""
        logger.info("Fetching Spacelift policies")

        query = """
        query GetPolicies {
            policies {
                id
                name
                type
                body
                space
                labels
            }
        }
        """

        try:
            data = await self.make_graphql_request(query)
            policies = data["data"]["policies"] or []
            if policies:
                yield policies
                logger.info(f"Fetched {len(policies)} policies")
            else:
                yield []
                logger.info("No policies found")

        except Exception as e:
            logger.error(
                f"Could not fetch policies - may require admin permissions: {e}"
            )
            yield []

    async def get_users(self) -> AsyncGenerator[List[Dict[str, Any]], None]:
        """Get all users."""
        logger.info("Fetching Spacelift users")

        query = """
        query GetBasicManagedUsers {
            managedUsers {
                id
                username
                invitationEmail
                status
                role
                lastLoginTime
            }
        }
        """

        try:
            data = await self.make_graphql_request(query)
            managed_users = data["data"]["managedUsers"] or []

            if managed_users:
                yield managed_users
                logger.info(f"Fetched {len(managed_users)} managed users")
            else:
                yield []
                logger.info("No managed users found")

        except Exception as e:
            logger.error(
                f"Could not fetch managed users - may require admin permissions: {e}"
            )
            yield []
