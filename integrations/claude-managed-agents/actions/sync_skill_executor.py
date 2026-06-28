from __future__ import annotations

from loguru import logger
from port_ocean.context.ocean import ocean
from port_ocean.core.models import ActionRun, WorkflowNodeRun

from actions.abstract_executor import AbstractAnthropicExecutor
from actions.skill_packaging import (
    claude_skill_raw_from_api,
    package_skill_files,
    skill_display_title,
)
from clients.port_catalog import fetch_skill_content
from integration import ObjectKind


class SyncSkillExecutor(AbstractAnthropicExecutor):
    """Upload a published Port skill to Claude and register a claude_skill entity.

    Two modes:
    - ``create``: creates a new Claude skill and links it to the Port _skill.
    - ``new_version``: adds a version to an existing Claude skill chosen by the user.
    """

    ACTION_NAME = "sync_skill"

    async def execute(self, run: ActionRun | WorkflowNodeRun) -> None:
        props = run.execution_properties
        port_skill_id = props.get("portSkillId")
        mode = props.get("mode", "create")
        claude_skill_id = props.get("claudeSkillId")

        if not isinstance(port_skill_id, str) or not port_skill_id:
            raise ValueError("portSkillId is required")
        if mode not in ("create", "new_version"):
            raise ValueError("mode must be 'create' or 'new_version'")
        if mode == "new_version" and not claude_skill_id:
            raise ValueError("claudeSkillId is required when mode is new_version")

        skill_content = await fetch_skill_content(port_skill_id)
        instructions = skill_content.get("instructions")
        if not isinstance(instructions, str) or not instructions:
            raise ValueError(
                f"Port skill {port_skill_id!r} has no instructions in its published version"
            )
        resources = skill_content.get("resources")

        packaged_files = package_skill_files(port_skill_id, instructions, resources)

        if mode == "new_version":
            await self.client.create_skill_version(
                claude_skill_id,  # type: ignore[arg-type]
                packaged_files,
            )
            api_skill = await self.client.get_skill(claude_skill_id)  # type: ignore[arg-type]
        else:
            display_title = skill_display_title(skill_content)
            api_skill = await self.client.create_skill(
                packaged_files,
                display_title=display_title,
            )
            claude_skill_id = api_skill["id"]

        raw = claude_skill_raw_from_api(api_skill)
        raw["port_skill_id"] = port_skill_id
        await self.register_entity(ObjectKind.SKILL, raw)

        latest_version = api_skill.get("latest_version")
        logger.info(
            f"Synced Port skill {port_skill_id!r} to Claude skill {claude_skill_id!r} "
            f"(version {latest_version})"
        )
        await ocean.port_client.report_run_completed(
            run,
            True,
            f"Synced skill {claude_skill_id} (version {latest_version})",
        )
