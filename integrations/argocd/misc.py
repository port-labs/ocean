from enum import StrEnum


class ObjectKind(StrEnum):
    PROJECT = "project"


class ResourceKindsWithSpecialHandling(StrEnum):
    DEPLOYMENT_HISTORY = "deployment-history"
    KUBERNETES_RESOURCE = "kubernetes-resource"
    MANAGED_RESOURCE = "managed-resource"
    CLUSTER = "cluster"
    APPLICATION = "application"
