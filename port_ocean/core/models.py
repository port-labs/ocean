from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum, StrEnum
from abc import ABC, abstractmethod
from typing import Any, Literal, NotRequired, TypeAlias, TypedDict
from pydantic.v1 import BaseModel, Extra, root_validator
from pydantic.v1.fields import Field


class EventListenerType(StrEnum):
    WEBHOOK = "WEBHOOK"
    KAFKA = "KAFKA"
    POLLING = "POLLING"
    ONCE = "ONCE"
    WEBHOOKS_ONLY = "WEBHOOKS_ONLY"
    ACTIONS_ONLY = "ACTIONS_ONLY"


class LiveEventsConsumerType(StrEnum):
    REDIS = "REDIS"


class CreatePortResourcesOrigin(StrEnum):
    Empty = "Empty"
    Ocean = "Ocean"
    Default = "Default"
    Port = "Port"


class ProcessExecutionMode(StrEnum):
    multi_process = "multi_process"
    single_process = "single_process"


class CachingStorageMode(StrEnum):
    disk = "disk"
    memory = "memory"


class Runtime(Enum):
    Saas = "Saas"
    OnPrem = "OnPrem"

    @property
    def is_saas_runtime(self) -> bool:
        return self in [Runtime.Saas]

    def is_installation_type_compatible(self, installation_type: str) -> bool:
        """
        Check if the installation type is compatible with the runtime

        if the runtime is Saas, the installation type should start with Saas
        else the installation type should be OnPrem
        """
        return (
            self.value == Runtime.Saas.value
            and installation_type.startswith(self.value)
        ) or installation_type == self.value


class PortAPIErrorMessage(Enum):
    NOT_FOUND = "not_found"


class Entity(BaseModel):
    identifier: Any
    icon: str | None
    blueprint: Any
    title: Any
    team: str | None | list[Any] | dict[str, Any] = []
    properties: dict[str, Any] = {}
    relations: dict[str, Any] = {}

    @property
    def is_using_search_identifier(self) -> bool:
        return isinstance(self.identifier, dict)

    @property
    def is_using_search_relation(self) -> bool:
        return any(
            isinstance(relation, dict) for relation in self.relations.values()
        ) or (
            self.team is not None and any(isinstance(team, dict) for team in self.team)
        )


class EntityBulkResult(TypedDict):
    identifier: str
    index: int
    created: bool


class EntityBulkError(TypedDict):
    identifier: str
    index: int
    statusCode: int
    error: str
    message: str


class BulkUpsertResponse(TypedDict):
    entities: list[EntityBulkResult]
    errors: list[EntityBulkError]


class BlueprintRelation(BaseModel):
    many: bool
    required: bool
    target: str
    title: str | None


class Blueprint(BaseModel):
    identifier: str
    title: str | None
    team: str | None
    properties_schema: dict[str, Any] = Field(alias="schema")
    relations: dict[str, BlueprintRelation]


class Migration(BaseModel):
    id: str
    actor: str
    sourceBlueprint: str
    mapping: dict[str, Any]
    status: str


@dataclass
class EntityPortDiff:
    """Represents the differences between entities for porting.

    This class holds the lists of deleted, modified, and created entities as part
    of the porting process.
    """

    deleted: list[Entity] = field(default_factory=list)
    modified: list[Entity] = field(default_factory=list)
    created: list[Entity] = field(default_factory=list)


class IntegrationFeatureFlag(StrEnum):
    USE_PROVISIONED_DEFAULTS = "USE_PROVISIONED_DEFAULTS"
    LAKEHOUSE_ELIGIBLE = "LAKEHOUSE_ELIGIBLE"
    OCEAN_KAFKA_INTEGRATION_RESYNC_REQUESTS_TOPIC_ENABLED = (
        "OCEAN_KAFKA_INTEGRATION_RESYNC_REQUESTS_TOPIC_ENABLED"
    )
    DATA_SOURCE_PROCESSOR_ENABLED = "DATA_SOURCE_PROCESSOR_ENABLED"
    LIVE_EVENTS_REDIS_STREAM_ENABLED = "LIVE_EVENTS_REDIS_STREAM_ENABLED"


class ProcessingMode(StrEnum):
    ocean_core = "ocean-core"
    dsp = "dsp"


class LakehouseOperation(StrEnum):
    UPSERT = "upsert"
    DELETE = "delete"


class LakehouseEventType(StrEnum):
    RESYNC = "resync"
    LIVE_EVENT = "live-event"


class RunStatus(StrEnum):
    IN_PROGRESS = "IN_PROGRESS"
    SUCCESS = "SUCCESS"
    FAILURE = "FAILURE"


# TODO: Rename RunStatus to that once this name is used in the integrations code
ActionRunStatus: TypeAlias = RunStatus


class WorkflowNodeRunStatus(StrEnum):
    IN_PROGRESS = "IN_PROGRESS"
    COMPLETED = "COMPLETED"


class WorkflowNodeRunResult(StrEnum):
    SUCCESS = "SUCCESS"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


class WorkflowNodeRunLog(BaseModel):
    level: Literal["INFO", "WARN", "ERROR", "DEBUG"]
    message: str


class RunKind(StrEnum):
    ACTION = "action"
    WORKFLOW_NODE = "workflow_node"


class IntegrationActionInvocationPayload(BaseModel):
    type: Literal["INTEGRATION_ACTION"]
    installationId: str
    integrationActionType: str
    integrationActionExecutionProperties: dict[str, Any]


class WorkflowIntegrationActionConfig(BaseModel):
    type: Literal["INTEGRATION_ACTION"]
    installationId: str
    integrationProvider: str
    integrationInvocationType: str
    integrationActionExecutionProperties: dict[str, Any]

    class Config:
        extra = Extra.allow


class IntegrationRun(ABC):
    """Abstract contract for integration runs (action runs and workflow node runs).

    Consumers operate through this interface and stay agnostic to the concrete
    run type. Use ``run_kind`` only for the rare cases that need to branch on type.
    """

    id: str

    @property
    @abstractmethod
    def run_kind(self) -> RunKind: ...

    @property
    @abstractmethod
    def action_type(self) -> str: ...

    @property
    @abstractmethod
    def execution_properties(self) -> dict[str, Any]: ...

    @property
    @abstractmethod
    def buffer_utilization_key(self) -> str: ...

    @property
    @abstractmethod
    def is_in_progress(self) -> bool: ...


class ActionRun(BaseModel, IntegrationRun):

    class Action(BaseModel):
        identifier: str

    class Config:
        allow_population_by_field_name = True

    id: str
    status: RunStatus
    payload: IntegrationActionInvocationPayload
    action: Action

    @property
    def run_kind(self) -> RunKind:
        return RunKind.ACTION

    @property
    def action_identifier(self) -> str:
        return self.action.identifier

    @property
    def action_type(self) -> str:
        return self.payload.integrationActionType

    @property
    def execution_properties(self) -> dict[str, Any]:
        return self.payload.integrationActionExecutionProperties

    @property
    def buffer_utilization_key(self) -> str:
        return self.action_identifier

    @property
    def is_in_progress(self) -> bool:
        return self.status == RunStatus.IN_PROGRESS


class WorkflowNodeRun(BaseModel, IntegrationRun):
    class WorkflowNode(BaseModel):
        config: WorkflowIntegrationActionConfig

    class Config:
        allow_population_by_field_name = True
        extra = Extra.allow

    id: str = Field(alias="identifier")
    node_uid: str = Field(alias="nodeUid")
    status: WorkflowNodeRunStatus
    config: WorkflowIntegrationActionConfig | None = None
    node: WorkflowNode | None = None
    output: dict[str, Any] = Field(default_factory=dict)

    @root_validator(skip_on_failure=True)
    def require_config_source(cls, values: dict[str, Any]) -> dict[str, Any]:
        config = values.get("config")
        node = values.get("node")
        has_node_config = node is not None and (
            node.config is not None or node.nodeConfig is not None
        )
        if config is None and not has_node_config:
            raise ValueError("either config or node.config must be provided")
        return values

    @property
    def integration_config(self) -> WorkflowIntegrationActionConfig:
        if self.config is not None:
            return self.config
        if self.node is not None:
            return self.node.config
        raise ValueError("either config or node.config must be provided")

    @property
    def run_kind(self) -> RunKind:
        return RunKind.WORKFLOW_NODE

    @property
    def action_type(self) -> str:
        return self.integration_config.integrationInvocationType

    @property
    def execution_properties(self) -> dict[str, Any]:
        return self.integration_config.integrationActionExecutionProperties

    @property
    def buffer_utilization_key(self) -> str:
        return self.node_uid

    @property
    def is_in_progress(self) -> bool:
        return self.status == WorkflowNodeRunStatus.IN_PROGRESS


class LakehouseDataEntryMetadata(TypedDict):
    operation: LakehouseOperation
    resource_index: int
    extraction_timestamp: int
    selector_hash: NotRequired[str | None]


class LakehouseDataEntry(TypedDict):
    request: dict[str, Any]
    response: dict[str, Any]
    metadata: LakehouseDataEntryMetadata
    items: list[Any]
    environment_data: NotRequired[dict[str, str | None]]


class LakehouseDataEntryBatch(TypedDict):
    event_id: str | None
    type: str | None
    kind: str
    event_type: LakehouseEventType
    resync_start_time: datetime | None
    extraction_timestamp: int
    data: list[LakehouseDataEntry]
