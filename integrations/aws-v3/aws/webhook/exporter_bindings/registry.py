from aws.webhook.exporter_bindings.binding import ExporterBinding
from aws.webhook.exporter_bindings.lambda_function import (
    BINDING as LAMBDA_FUNCTION_BINDING,
)
from aws.webhook.exporter_bindings.s3_bucket import BINDING as S3_BUCKET_BINDING

_ALL_BINDINGS: tuple[ExporterBinding, ...] = (
    S3_BUCKET_BINDING,
    LAMBDA_FUNCTION_BINDING,
)

EXPORTER_REGISTRY: dict[str, ExporterBinding] = {
    binding.kind: binding for binding in _ALL_BINDINGS
}
