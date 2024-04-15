from typing import Any

from pydantic import BaseModel


class CloudAssetInventoryFeed:
    id: str
    asset_types: str
    topic_name: str


class FeedEvent(BaseModel):
    message_id: str
    asset_name: str
    asset_type: str
    data: dict[Any, Any]

    @property
    def metadata(self) -> dict[str, Any]:
        return self.dict(exclude={"data"})
