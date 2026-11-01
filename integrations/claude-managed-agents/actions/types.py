from typing import Any, Self

from anthropic.types.beta.beta_managed_agents_session import BetaManagedAgentsSession
from anthropic.types.beta.beta_managed_agents_session_usage import (
    BetaManagedAgentsSessionUsage,
)
from anthropic.types.beta_monetary_amount import BetaMonetaryAmount
from pydantic import BaseModel, ConfigDict, Field


def list_cost_to_usd(list_cost: BetaMonetaryAmount | None) -> float | None:
    if list_cost is None:
        return None
    try:
        return float(list_cost.amount) / 100.0
    except (TypeError, ValueError):
        return None


def _token_delta(current: int | None, baseline: int | None) -> int | None:
    if current is None:
        return None
    if baseline is None:
        return current
    return max(0, current - baseline)


def _cost_delta(current: float | None, baseline: float | None) -> float | None:
    if current is None:
        return None
    if baseline is None:
        return current
    return max(0.0, round(current - baseline, 2))


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
        baseline_usage: BetaManagedAgentsSessionUsage,
    ) -> Self:
        input_tokens = session.usage.input_tokens
        output_tokens = session.usage.output_tokens
        cost = list_cost_to_usd(session.usage.list_cost)
        if baseline_usage is not None:
            input_tokens = _token_delta(input_tokens, baseline_usage.input_tokens)
            output_tokens = _token_delta(output_tokens, baseline_usage.output_tokens)
            cost = _cost_delta(cost, list_cost_to_usd(baseline_usage.list_cost))

        return cls(
            session_id=session_id,
            user_message_event_id=user_message_event_id,
            url=url,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            cost_usd=(cost),
        )
