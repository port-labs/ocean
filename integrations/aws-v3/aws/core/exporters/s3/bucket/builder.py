from aws.core.exporters.s3.bucket.models import S3Bucket, S3BucketProperties
from typing import Dict, Any, Self


class S3BucketBuilder:
    def __init__(self, name: str) -> None:
        self._bucket = S3Bucket(Properties=S3BucketProperties())

    def with_data(self, data: Dict[str, Any]) -> Self:
        for k, v in data.items():
            setattr(self._bucket.Properties, k, v)
        return self

    def build(self) -> S3Bucket:
        return self._bucket
