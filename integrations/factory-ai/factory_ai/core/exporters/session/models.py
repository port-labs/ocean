"""Factory Droid Sessions API models.

See https://docs.factory.com/api-reference/sessions
"""

from __future__ import annotations

from pydantic import BaseModel, Field

from factory_ai.core.models import FactoryListOptions, FactoryModel, FactoryPagination

# OpenAPI allows 1–100; use the max page size for lean resyncs.
_DEFAULT_LIST_LIMIT = 100


class ListSessionOptions(FactoryListOptions):
    """Options for ``GET /api/v0/sessions``.

    ``cursor`` is owned by the exporter's pagination loop, not OOTB selectors.
    """

    limit: int | None = Field(_DEFAULT_LIST_LIMIT, alias="limit")
    computer_id: str | None = Field(None, alias="computerId")


class GetSessionOptions(BaseModel):
    session_id: str
    computer_id: str | None = None


class SessionTag(FactoryModel):
    name: str
    metadata: dict[str, str] | None = None


class SessionWorktree(FactoryModel):
    repo_root: str = Field(alias="repoRoot")
    branch: str | None = None
    lifecycle: str | None = None
    path: str | None = None
    parent_worktree_path: str | None = Field(None, alias="parentWorktreePath")
    removed_at: str | None = Field(None, alias="removedAt")
    setup_profile_id: str | None = Field(None, alias="setupProfileId")


class SessionSettings(FactoryModel):
    model: str | None = None
    reasoning_effort: str | None = Field(None, alias="reasoningEffort")
    interaction_mode: str | None = Field(None, alias="interactionMode")
    autonomy_level: str | None = Field(None, alias="autonomyLevel")
    autonomy_mode: str | None = Field(None, alias="autonomyMode")
    spec_mode_model: str | None = Field(None, alias="specModeModel")
    spec_mode_reasoning_effort: str | None = Field(
        None, alias="specModeReasoningEffort"
    )
    provider_lock: str | None = Field(None, alias="providerLock")
    provider_lock_timestamp: str | None = Field(None, alias="providerLockTimestamp")
    api_provider_lock: str | None = Field(None, alias="apiProviderLock")
    archived_at: str | None = Field(None, alias="archivedAt")
    tags: list[SessionTag] | None = None
    worktree: SessionWorktree | None = None
    enabled_tool_ids: list[str] | None = Field(None, alias="enabledToolIds")
    disabled_tool_ids: list[str] | None = Field(None, alias="disabledToolIds")
    restrict_tool_ids: list[str] | None = Field(None, alias="restrictToolIds")
    tool_execution_mode: str | None = Field(None, alias="toolExecutionMode")
    allow_subagents_in_scripts: bool | None = Field(
        None, alias="allowSubagentsInScripts"
    )
    compaction_model: str | None = Field(None, alias="compactionModel")
    compaction_threshold_check_enabled: bool | None = Field(
        None, alias="compactionThresholdCheckEnabled"
    )


class SessionArtifact(FactoryModel):
    id: str
    url: str
    provider: str
    kind: str
    source: str
    created_at: str = Field(alias="createdAt")
    title: str | None = None
    external_id: str | None = Field(None, alias="externalId")
    connector: str | None = None
    file_role: str | None = Field(None, alias="fileRole")
    action: str | None = None
    tool_call_id: str | None = Field(None, alias="toolCallId")


class Session(FactoryModel):
    """Droid session from the Factory Sessions API.

    List and get share this shape. ``parent_session_id`` is snake_case in the
    OpenAPI contract (unlike the surrounding camelCase fields).
    """

    session_id: str = Field(alias="sessionId")
    status: str
    message_count: int = Field(alias="messageCount")
    created_at: int = Field(alias="createdAt")
    updated_at: int = Field(alias="updatedAt")
    parent_session_id: str | None = None
    title: str | None = None
    completed_at: int | None = Field(None, alias="completedAt")
    computer_id: str | None = Field(None, alias="computerId")
    session_settings: SessionSettings | None = Field(None, alias="sessionSettings")
    artifacts: list[SessionArtifact] | None = None
    factory_credits: float | None = Field(None, alias="factoryCredits")


class ListSessionsResponse(FactoryModel):
    sessions: list[Session]
    pagination: FactoryPagination
