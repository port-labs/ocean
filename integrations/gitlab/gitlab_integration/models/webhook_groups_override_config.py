from pydantic import BaseModel


class WebhookGroupConfig(BaseModel):
    events: list[str]


class WebhookTokenConfig(BaseModel):
    groups: dict[str, WebhookGroupConfig]


class WebhookMappingConfig(BaseModel):
    tokens: dict[str, WebhookTokenConfig]

    def get_token_groups(self, token: str) -> dict[str, WebhookGroupConfig]:
        if self.tokens.get(token):
            return self.tokens[token].groups
        else:
            return {}
