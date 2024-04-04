from pydantic import BaseModel


class WebhookGroupConfig(BaseModel):
    events: list[str]


class WebhookTokenConfig(BaseModel):
    groups: dict[str, WebhookGroupConfig]


class WebhookMappingConfig(BaseModel):
    tokens: dict[str, WebhookTokenConfig]
