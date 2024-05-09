import enum


ACCOUNT_ID_PROPERTY = "__AccountId"
KIND_PROPERTY = "__Kind"
REGION_PROPERTY = "__Region"


class ResourceKinds(enum.StrEnum):
    ACCOUNT = "account"
    CLOUD_CONTROL_RESOURCE = "cloudResource"
