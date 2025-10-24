from typing import List
from pydantic import BaseModel


class SubscriptionIds(BaseModel):
    subscription_ids: List[str]


class AzureAPIOptions(BaseModel):
    api_version: str


class ResourceGraphExporterOptions(AzureAPIOptions):
    query: str
    subscriptions: List[str]


class SubscriptionExporterOptions(AzureAPIOptions): ...
