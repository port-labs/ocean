from typing import List
from pydantic import BaseModel


class SubscriptionIds(BaseModel):
    subscription_ids: List[str]


class ResourceGraphExporterOptions(BaseModel):
    query: str
    subscriptions: List[str]


class SubscriptionExporterOptions(BaseModel): ...
