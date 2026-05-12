"""AWS-V3 live events package.

This package implements the event-driven update path for the AWS-V3 integration,
sitting alongside the poll-based resync flow. See `docs/adr-live-events.md` for
the architecture decision record.

The package is intentionally inert at import time: nothing is registered with
Ocean until `register_live_events_webhooks()` from `aws.webhook.registry` is
called from `main.py`.
"""
