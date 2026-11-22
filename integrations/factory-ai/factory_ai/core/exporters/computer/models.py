"""Factory Computers API models.

See https://docs.factory.com/api-reference/computers
"""

from __future__ import annotations

from pydantic import BaseModel, Field

from factory_ai.core.models import FactoryListOptions, FactoryModel


class ListComputerOptions(FactoryListOptions):
    """Options for ``GET /api/v0/computers``.

    Bool flags default to ``None`` (omit from the query). Set ``True``/``False``
    explicitly when callers need to force include/exclude behavior.
    """

    service_account_id: str | None = Field(None, alias="serviceAccountId")
    host_id: str | None = Field(None, alias="hostId")
    include_provisioning_steps: bool | None = Field(
        None, alias="includeProvisioningSteps"
    )
    include_unlisted: bool | None = Field(None, alias="includeUnlisted")


class GetComputerOptions(BaseModel):
    computer_id: str


class ComputerDisk(FactoryModel):
    avail_bytes: int = Field(alias="availBytes")
    total_bytes: int = Field(alias="totalBytes")
    avail_inodes: int = Field(alias="availInodes")
    total_inodes: int = Field(alias="totalInodes")
    band: str
    sampled_at: float = Field(alias="sampledAt")


class ComputerProvisioningStep(FactoryModel):
    id: str
    name: str
    status: str
    error: str | None = None
    started_at: float | None = Field(None, alias="startedAt")
    completed_at: float | None = Field(None, alias="completedAt")
    install_session_id: str | None = Field(None, alias="installSessionId")


class ComputerIdentity(FactoryModel):
    public_key: str = Field(alias="publicKey")
    key_id: str = Field(alias="keyId")
    algorithm: str
    updated_at: float = Field(alias="updatedAt")


class ComputerSource(FactoryModel):
    """Provenance of a computer.

    Create accepts ``kind: environment`` with ``environmentId``; list/get may
    also return ``template`` / ``execution-template`` / ``computer``. Unknown
    fields are retained via ``FactoryModel`` for forward-compatible mappings.
    """

    kind: str
    environment_id: str | None = Field(None, alias="environmentId")
    template_id: str | None = Field(None, alias="templateId")
    computer_id: str | None = Field(None, alias="computerId")


class Computer(FactoryModel):
    id: str
    name: str
    provider_type: str = Field(alias="providerType")
    created_at: float = Field(alias="createdAt")
    host_id: str | None = Field(None, alias="hostId")
    is_listed: bool | None = Field(None, alias="isListed")
    status: str | None = None
    provider_status: str | None = Field(None, alias="providerStatus")
    last_seen_at: float | None = Field(None, alias="lastSeenAt")
    disk: ComputerDisk | None = None
    provisioning_steps: list[ComputerProvisioningStep] | None = Field(
        None, alias="provisioningSteps"
    )
    relay_client_url: str | None = Field(None, alias="relayClientUrl")
    relay_agent_url: str | None = Field(None, alias="relayAgentUrl")
    computer_identity: ComputerIdentity | None = Field(None, alias="computerIdentity")
    remote_user: str | None = Field(None, alias="remoteUser")
    cloned_repo_directories: list[str] | None = Field(
        None, alias="clonedRepoDirectories"
    )
    owner_principal_kind: str | None = Field(None, alias="ownerPrincipalKind")
    owner_id: str | None = Field(None, alias="ownerId")
    computer_source: ComputerSource | None = Field(None, alias="computerSource")


class ListComputersResponse(FactoryModel):
    computers: list[Computer]
