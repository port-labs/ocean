from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum, StrEnum
from typing import Any, Literal, NotRequired, Protocol, TypedDict, runtime_checkable
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


class IntegrationActionInvocation(BaseModel):
    type: Literal["INTEGRATION_ACTION"] = "INTEGRATION_ACTION"
    installationId: str = ""
    integrationActionType: str = ""
    integrationInvocationType: str = ""
    integrationActionExecutionProperties: dict[str, Any] = Field(default_factory=dict)
    integrationProvider: str | None = None

    class Config:
        extra = Extra.allow
        allow_population_by_field_name = True

    @property
    def action_type(self) -> str:
        return self.integrationActionType or self.integrationInvocationType


IntegrationActionInvocationPayload = IntegrationActionInvocation


@runtime_checkable
class IntegrationRun(Protocol):
    """Shared execution contract for action runs and workflow node runs."""

    output: dict[str, Any]

    @property
    def kind(self) -> RunKind: ...

    @property
    def id(self) -> str: ...

    @property
    def status(self) -> RunStatus | WorkflowNodeRunStatus: ...

    @property
    def action_type(self) -> str: ...

    @property
    def execution_properties(self) -> dict[str, Any]: ...

    @property
    def buffer_utilization_key(self) -> str | None: ...

    @property
    def is_action_run(self) -> bool: ...

    @property
    def is_workflow_node_run(self) -> bool: ...


class ActionRun(BaseModel):
    id: str
    status: RunStatus
    payload: IntegrationActionInvocation
    action_identifier: str = Field(default="", alias="actionIdentifier")
    output: dict[str, Any] = Field(default_factory=dict)

    class Config:
        allow_population_by_field_name = True

    @property
    def kind(self) -> RunKind:
        return RunKind.ACTION

    @property
    def action_type(self) -> str:
        return self.payload.action_type

    @property
    def execution_properties(self) -> dict[str, Any]:
        return self.payload.integrationActionExecutionProperties

    @property
    def buffer_utilization_key(self) -> str | None:
        return self.action_identifier or None

    @property
    def is_action_run(self) -> bool:
        return True

    @property
    def is_workflow_node_run(self) -> bool:
        return False


class WorkflowNodeRun(BaseModel):
    id: str = ""
    identifier: str = ""
    status: WorkflowNodeRunStatus
    config: IntegrationActionInvocation | None = None
    output: dict[str, Any] = Field(default_factory=dict)
    result: WorkflowNodeRunResult | None = None
    installationId: str | None = None

    class Config:
        allow_population_by_field_name = True

    @root_validator(pre=True)
    def normalize_api_shapes(cls, values: dict[str, Any]) -> dict[str, Any]:
        run_id = values.get("id") or values.get("identifier")
        if run_id:
            values["id"] = run_id
            values["identifier"] = run_id

        node = values.get("node")
        if isinstance(node, dict) and node.get("config") and not values.get("config"):
            values["config"] = node["config"]

        return values

    @property
    def kind(self) -> RunKind:
        return RunKind.WORKFLOW_NODE

    @property
    def action_type(self) -> str:
        return self.config.action_type if self.config else ""

    @property
    def execution_properties(self) -> dict[str, Any]:
        if self.config is None:
            return {}
        return self.config.integrationActionExecutionProperties

    @property
    def buffer_utilization_key(self) -> str | None:
        if self.config is None:
            return None
        return self.config.integrationInvocationType or None

    @property
    def is_action_run(self) -> bool:
        return False

    @property
    def is_workflow_node_run(self) -> bool:
        return True


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
