from typing import Optional, Dict, Any, List
from pydantic import BaseModel, Field


class ECSClusterProperties(BaseModel, extra="forbid"):
    clusterArn: Optional[str] = None
    clusterName: Optional[str] = None
    status: Optional[str] = None
    activeServicesCount: Optional[int] = None
    pendingTasksCount: Optional[int] = None
    runningTasksCount: Optional[int] = None
    registeredContainerInstancesCount: Optional[int] = None
    capacityProviders: Optional[List[str]] = None
    defaultCapacityProviderStrategy: Optional[List[Dict[str, Any]]] = None
    settings: Optional[List[Dict[str, Any]]] = None
    configuration: Optional[Dict[str, Any]] = None
    statistics: Optional[List[Dict[str, Any]]] = None
    tags: Optional[List[Dict[str, Any]]] = None
    attachments: Optional[List[Dict[str, Any]]] = None
    attachmentsStatus: Optional[str] = None
    serviceConnectDefaults: Optional[Dict[str, Any]] = None
    pendingTaskArns: Optional[List[str]] = None


class ECSCluster(BaseModel, extra="ignore"):
    Type: str = "AWS::ECS::Cluster"
    Properties: ECSClusterProperties = Field(default_factory=ECSClusterProperties)
