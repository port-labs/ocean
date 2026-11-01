from typing import Any, Self

from anthropic.types.beta.beta_managed_agents_session import BetaManagedAgentsSession
from anthropic.types.beta.beta_managed_agents_session_usage import (
    BetaManagedAgentsSessionUsage,
)
from anthropic.types.beta.sessions.beta_managed_agents_session_usage_snapshot import (
    BetaManagedAgentsSessionUsageSnapshot,
)
from pydantic import BaseModel, ConfigDict, Field

SessionUsageLike = (
    BetaManagedAgentsSessionUsage | BetaManagedAgentsSessionUsageSnapshot | None
)


def list_cost_to_usd(list_cost: Any) -> float | None:
    """Convert Anthropic ``usage.list_cost`` (cents string) to USD.

    Anthropic reports ``list_cost`` as ``{"amount": "<cents>", "currency": "USD"}``
    (or a ``BetaMonetaryAmount`` model) where ``amount`` is whole US cents at
    public list rates (not contracted price).
    """
    if list_cost is None:
        return None
    if isinstance(list_cost, dict):
        amount = list_cost.get("amount")
    else:
        amount = getattr(list_cost, "amount", None)
    if amount is None:
        return None
    try:
        return int(amount) / 100.0
    except (TypeError, ValueError):
        return None


def _token_delta(current: int | None, baseline: int | None) -> int | None:
    if current is None:
        return None
    return max(0, current - (baseline or 0))


def _cost_delta(current: Any, baseline: Any) -> float | None:
    current_usd = list_cost_to_usd(current)
    if current_usd is None:
        return None
    baseline_usd = list_cost_to_usd(baseline) or 0.0
    return max(0.0, round(current_usd - baseline_usd, 2))


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
        baseline_usage: SessionUsageLike = None,
    ) -> Self:
        """Build output from a session retrieve, as cost/tokens for this trigger.

        Anthropic session ``usage`` is cumulative. Pass ``baseline_usage`` from the
        prior ``session.usage`` snapshot (last idle) to report only this
        invocation's delta; omit it for a brand-new session.
        """
        usage = session.usage
        baseline = baseline_usage
        return cls(
            session_id=session_id,
            user_message_event_id=user_message_event_id,
            url=url,
            input_tokens=_token_delta(
                usage.input_tokens,
                None if baseline is None else baseline.input_tokens,
            ),
            output_tokens=_token_delta(
                usage.output_tokens,
                None if baseline is None else baseline.output_tokens,
            ),
            cost_usd=_cost_delta(
                usage.list_cost,
                None if baseline is None else baseline.list_cost,
            ),
        )
