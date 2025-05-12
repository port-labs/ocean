from dataclasses import dataclass
from typing import Any

from aws.helpers.models import CustomProperties, MaterializedResource, AWS_RAW_ITEM


@dataclass(slots=True)
class ResyncContext:
    """Runtime information computed *once* per resync call."""

    kind: str
    account_id: str
    region: str

    def enrich(self, payload: AWS_RAW_ITEM) -> MaterializedResource:
        payload.update(
            {
                CustomProperties.KIND.value: self.kind,
                CustomProperties.ACCOUNT_ID.value: self.account_id,
                CustomProperties.REGION.value: self.region,
            }
        )
        return payload
