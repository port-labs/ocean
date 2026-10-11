from typing import Any, Self

from anthropic.types.beta.beta_managed_agents_session import BetaManagedAgentsSession
from pydantic import BaseModel, ConfigDict, Field


def list_cost_to_usd(list_cost: Any) -> float | None:
    """Convert Anthropic ``usage.list_cost`` (cents string) to USD.

    Anthropic reports ``list_cost`` as ``{"amount": "<cents>", "currency": "USD"}``
    where ``amount`` is whole US cents at public list rates (not contracted price).
    """
    if not isinstance(list_cost, dict):
        return None
    amount = list_cost.get("amount")
    if amount is None:
        return None
    try:
        return int(amount) / 100.0
    except (TypeError, ValueError):
        return None


class TriggerAgentSessionOutput(BaseModel):
    """Standard ``trigger_agent`` run-output fields for a Claude session."""

    model_config = ConfigDict(extra="ignore", serialize_by_alias=True)

    session_id: str | None = Field(default=None, serialization_alias="sessionId")
    user_message_event_id: str | None = Field(
        default=None, serialization_alias="userMessageEventId"
    )
    url: str
    input_tokens: int | None = Field(default=None, serialization_alias="inputTokens")
    output_tokens: int | None = Field(default=None, serialization_alias="outputTokens")
    cost_usd: float | None = Field(default=None, serialization_alias="costUsd")

    def model_dump(self, **kwargs: Any) -> dict[str, Any]:
        return super().model_dump(**kwargs, exclude_none=True)

    @classmethod
    def from_session(
        cls,
        *,
        url: str,
        session: BetaManagedAgentsSession,
        session_id: str | None = None,
        user_message_event_id: str | None = None,
    ) -> Self:
        """Build output from a session URL and session retrieve result."""
        return cls(
            session_id=session_id,
            user_message_event_id=user_message_event_id,
            url=url,
            input_tokens=session.usage.input_tokens,
            output_tokens=session.usage.output_tokens,
            # ``list_cost`` is on the API usage object but not yet a typed SDK field;
            # the SDK keeps it in pydantic extras (``extra="allow"``).
            cost_usd=list_cost_to_usd(getattr(session.usage, "list_cost", None)),
        )
