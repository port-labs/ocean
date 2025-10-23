from pydantic import BaseModel, PrivateAttr
from dateutil.parser import parse
from datetime import datetime, timezone, timedelta
from typing import Optional, Any


class AzureAccessToken(BaseModel):
    token: str
    expires_at: Optional[str] = None
    _time_buffer: timedelta = PrivateAttr(default_factory=lambda: timedelta(minutes=5))

    @property
    def is_expired(self) -> bool:
        if not self.expires_at:
            return False

        expires_at_dt = parse(self.expires_at)
        return datetime.now(timezone.utc) >= (expires_at_dt - self._time_buffer)


class TokenCredential:

    async def get_token(
        self,
        *scopes: str,
        claims: Optional[str] = None,
        tenant_id: Optional[str] = None,
        enable_cae: bool = False,
        **kwargs: Any,
    ) -> AzureAccessToken:
        return AzureAccessToken(token="token", expires_at="2025-01-01T00:00:00Z")
