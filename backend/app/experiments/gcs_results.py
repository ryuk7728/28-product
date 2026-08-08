from __future__ import annotations

from dataclasses import dataclass
import gzip
import hashlib
import json
from pathlib import PurePosixPath
from typing import Any


@dataclass(frozen=True)
class GcsLocation:
    bucket: str
    prefix: str


def parse_gcs_uri(uri: str) -> GcsLocation:
    if not uri.startswith("gs://"):
        raise ValueError("GCS output prefix must start with gs://")
    remainder = uri[5:]
    bucket, separator, prefix = remainder.partition("/")
    if not bucket:
        raise ValueError("GCS output prefix is missing a bucket name.")
    return GcsLocation(bucket=bucket, prefix=prefix.strip("/") if separator else "")


def shard_object_name(
    *,
    prefix: str,
    run_id: str,
    policy_id: str,
    key_index: int,
    canonical_key_id: str,
    sample_start: int,
    sample_count: int,
) -> str:
    end = sample_start + sample_count - 1
    path = PurePosixPath(prefix) if prefix else PurePosixPath()
    path /= run_id
    path /= policy_id
    path /= f"key-{key_index:04d}-{canonical_key_id[:12]}"
    path /= f"samples-{sample_start:03d}-{end:03d}.ndjson.gz"
    return path.as_posix()


def encode_rows(rows: list[dict[str, Any]]) -> bytes:
    raw = b"".join(
        json.dumps(row, ensure_ascii=True, separators=(",", ":")).encode("utf-8")
        + b"\n"
        for row in rows
    )
    return gzip.compress(raw, compresslevel=6, mtime=0)


class GcsShardStore:
    def __init__(self, uri_prefix: str) -> None:
        from google.cloud import storage

        self.location = parse_gcs_uri(uri_prefix)
        self.client = storage.Client()
        self.bucket = self.client.bucket(self.location.bucket)

    def exists(self, object_name: str) -> bool:
        return self.bucket.blob(object_name).exists(client=self.client)

    def upload_immutable(
        self,
        object_name: str,
        rows: list[dict[str, Any]],
    ) -> dict[str, Any]:
        from google.api_core.exceptions import PreconditionFailed

        payload = encode_rows(rows)
        sha256 = hashlib.sha256(payload).hexdigest()
        blob = self.bucket.blob(object_name)
        blob.content_type = "application/x-ndjson"
        blob.content_encoding = "gzip"
        blob.metadata = {
            "sha256": sha256,
            "result_count": str(len(rows)),
        }
        try:
            blob.upload_from_string(payload, if_generation_match=0)
            disposition = "created"
        except PreconditionFailed:
            blob.reload(client=self.client)
            disposition = "already-exists"
        return {
            "uri": f"gs://{self.location.bucket}/{object_name}",
            "disposition": disposition,
            "result_count": len(rows),
            "sha256": sha256,
        }
