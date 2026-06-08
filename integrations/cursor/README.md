# Cursor Integration

Port Ocean integration for Cursor analytics and usage APIs.

## Supported resources

- `cursor-ai-commit-metric`
- `cursor-ai-change-metric`
- `cursor-daily-usage`
- `cursor-usage-event`

## Configuration

See `.port/spec.yaml` for complete configuration fields.

## Selector date configuration

- Analytics endpoints use relative dates (for example `30d` to `0d`).
- Admin endpoints use absolute UTC dates (`YYYY-MM-DD`).
- Both selector types enforce Cursor's max 30-day date window.
