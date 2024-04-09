from typing import Any, Dict

from pydantic import BaseModel


class CloudAssetInventoryFeed:
    id: str
    asset_types: str
    topic_name: str


class SubscriptionMessage(BaseModel):
    message_id: str
    asset_name: str
    asset_type: str
    data: dict[Any, Any]

    @property
    def metadata(self) -> Dict[str, Any]:
        return self.dict(exclude={"data"})
