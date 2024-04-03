from pydantic import BaseModel


class WebhookGroup(BaseModel):
    events: list[str]


class WebhookToken(BaseModel):
    groups: dict[str, WebhookGroup]


class TokenWebhookMapping(BaseModel):
    tokens: dict[str, WebhookToken]

    def get_token_groups(self, token: str) -> dict[str, WebhookGroup]:
        if self.tokens.get(token):
            return self.tokens[token].groups
        else:
            return {}
