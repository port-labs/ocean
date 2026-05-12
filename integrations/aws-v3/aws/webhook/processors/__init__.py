"""Per-kind AWS webhook processors and their shared abstract base.

Each concrete processor is a thin subclass of `AwsAbstractWebhookProcessor`
that wires:

* a single `ObjectKind` (`_kind`),
* the matching `IResourceExporter` subclass (`_exporter_cls`), and
* an identifier extractor (`_extract_identifier`) that knows the per-kind
  shape of the EventBridge envelope.

The base class owns authentication, validation, idempotency, region-policy
gating, session lookup, and the upsert/delete dispatch.
"""
