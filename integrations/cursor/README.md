# Cursor Integration

Port Ocean integration for Cursor analytics and usage APIs.

## Supported resources

- `cursor-team-model-usage`
- `cursor-user-model-usage`
- `cursor-daily-usage`
- `cursor-usage-event`

## Configuration

See `.port/spec.yaml` for complete configuration fields.

## Selector date configuration

- Analytics endpoints use relative dates (for example `30d` to `0d`).
- Admin endpoints use epoch-millisecond UTC timestamps (derived from relative selectors).
- Both selector types enforce Cursor's max 30-day date window.
