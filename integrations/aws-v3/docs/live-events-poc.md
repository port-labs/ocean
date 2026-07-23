# AWS-v3 Live Events — Thin POC (S3 Bucket only)

> **Status:** POC / not production-ready
> **Branch:** `poc/aws-v3-live-events-s3`
> **Scope:** `AWS::S3::Bucket` create/delete only
> See [`live-events-project.md`](./live-events-project.md) for the full project plan this POC validates.

## What this POC proves

That the API Destination → webhook → exporter re-fetch flow works end-to-end for a
single kind, using Ocean's existing `AbstractWebhookProcessor` framework, without
building out the full registry/parser/dedupe infrastructure described in the
project brief.

## What's included

- `aws/events/cloudtrail_parser.py` — parses an EventBridge envelope (with the
  CloudTrail event under `detail`) into a normalized `S3BucketLiveEvent`.
  Only `CreateBucket` and `DeleteBucket` are recognized; everything else is
  ignored.
- `aws/events/s3_bucket_webhook_processor.py` — an `AbstractWebhookProcessor`
  registered on `POST /webhook`:
  - `authenticate`: compares the `x-port-aws-ocean-api-key` header against the
    `liveEventsApiKey` integration config.
  - `validate_payload` / `should_process_event`: only accept parsable S3
    bucket create/delete events.
  - `handle_event`:
    - `DeleteBucket` → emits a deleted-raw-result keyed by bucket name.
    - `CreateBucket` → resolves a session for the event's account via
      `get_session_for_account`, then calls `S3BucketExporter.get_resource()`
      to fetch full, authoritative bucket details (mirrors resync behavior).
      Access-denied / not-found errors are treated as "bucket doesn't exist
      (anymore)" and result in a delete.
- `aws/auth/session_factory.get_session_for_account()` — naive helper that
  walks configured account sessions looking for a match. Fine for a couple of
  accounts; **not** how this should work in production (see "Known
  limitations" below and the project brief's session-factory task).
- `liveEventsApiKey` added to `.port/spec.yaml` as an optional, sensitive
  config value.
- Unit tests: `tests/events/test_cloudtrail_parser.py`,
  `tests/events/test_s3_bucket_webhook_processor.py`.

## What's intentionally NOT included (out of scope for this POC)

- Any kind other than S3 bucket.
- The exporter/kind registry described in the project brief (one processor,
  hardcoded, is enough to prove the pattern).
- Deduplication (TTL or otherwise) — a replayed event will just re-fetch and
  overwrite with the same state, which is harmless but wasteful.
- Retry/backoff tuning beyond `AbstractWebhookProcessor` defaults.
- Customer-facing IaC (CloudFormation/Terraform) for the EventBridge rule +
  API Destination + Connection. See the manual setup below to test locally.
- Toggling `saas.liveEvents.enabled` — left `false` since this isn't meant to
  ship as-is.

## Manually exercising the POC

1. Run the integration locally with `liveEventsApiKey` set, e.g. in
   `.env`:
   ```
   OCEAN__INTEGRATION__CONFIG__LIVE_EVENTS_API_KEY=test-secret
   ```
2. Send a synthetic "create bucket" event:
   ```bash
   curl -X POST http://localhost:8000/webhook \
     -H "content-type: application/json" \
     -H "x-port-aws-ocean-api-key: test-secret" \
     -d '{
           "account": "111122223333",
           "region": "us-east-1",
           "detail": {
             "eventName": "CreateBucket",
             "awsRegion": "us-east-1",
             "recipientAccountId": "111122223333",
             "requestParameters": {"bucketName": "my-test-bucket"}
           }
         }'
   ```
3. Send a "delete bucket" event the same way with `"eventName": "DeleteBucket"`.

In production, this payload shape is exactly what an EventBridge API
Destination delivers when its input transformer is left as pass-through and
the target is configured to POST the full `$.detail` context... in practice,
you'd typically configure the EventBridge rule with an input transformer to
shape the body; this POC assumes the default full-event envelope for
simplicity.

## Known limitations

- `get_session_for_account` iterates every configured account per event —
  O(accounts) per live event. Needs a real lookup/cache before this scales.
- No dedupe: duplicate deliveries (EventBridge/API Destination is at-least-once)
  just cause redundant re-fetches.
- No signature verification beyond a static shared secret — matches the
  project brief's stated v1 approach, but is worth revisiting.
- Single kind only; adding more kinds means generalizing the parser and
  processor into the registry pattern from the project brief.
