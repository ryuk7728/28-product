from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any


MIN_CONTRACT = 14
MAX_CONTRACT = 28
EXPECTED_KEYS = 2262


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Build the compact pooled and position-aware bot bidding lookup."
    )
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument(
        "--output",
        type=Path,
        default=Path(__file__).resolve().parents[1] / "bots" / "data" / "bid_stats_v2.json",
    )
    return parser


def _counts(bucket: object, *, key_text: str, label: str, expected_records: int) -> list[int]:
    if not isinstance(bucket, dict):
        raise RuntimeError(f"Missing {label} stats for {key_text!r}.")
    completed = bucket.get("completed")
    records = bucket.get("records")
    histogram = bucket.get("histogram")
    if type(records) is not int or records != expected_records:
        raise RuntimeError(f"Expected {expected_records} records in {label} for {key_text!r}.")
    if type(completed) is not int or not 0 <= completed <= records:
        raise RuntimeError(f"Invalid completed count in {label} for {key_text!r}.")
    if (
        not isinstance(histogram, list)
        or len(histogram) != MAX_CONTRACT + 1
        or any(type(count) is not int or count < 0 for count in histogram)
        or sum(histogram) != completed
    ):
        raise RuntimeError(f"Invalid histogram in {label} for {key_text!r}.")
    return [
        completed,
        *(sum(histogram[contract:]) for contract in range(MIN_CONTRACT, MAX_CONTRACT + 1)),
    ]


def build_lookup(source_path: Path) -> dict[str, Any]:
    source_bytes = source_path.read_bytes()
    source = json.loads(source_bytes)
    meta = source.get("meta")
    catalog = source.get("catalog")
    stats = source.get("stats")
    if not isinstance(meta, dict) or meta.get("isComplete") is not True:
        raise RuntimeError("Source dataset is not marked complete.")
    if not isinstance(catalog, list) or len(catalog) != EXPECTED_KEYS:
        raise RuntimeError(f"Expected {EXPECTED_KEYS} catalog keys.")
    if not isinstance(stats, dict):
        raise RuntimeError("Source dataset has no stats mapping.")

    keys: dict[str, list[list[int]]] = {}
    for key_text in catalog:
        if not isinstance(key_text, str) or key_text in keys:
            raise RuntimeError(f"Invalid or duplicate catalog key: {key_text!r}")
        entry = stats.get(key_text)
        positions = entry.get("positions") if isinstance(entry, dict) else None
        if not isinstance(entry, dict) or not isinstance(positions, dict):
            raise RuntimeError(f"Missing stats for {key_text!r}.")
        keys[key_text] = [
            _counts(entry.get("all"), key_text=key_text, label="pooled", expected_records=100),
            *(
                _counts(positions.get(str(position)), key_text=key_text, label=f"position {position}", expected_records=25)
                for position in range(1, 5)
            ),
        ]
    if set(keys) != set(stats):
        raise RuntimeError("Catalog and stats mappings do not contain identical keys.")
    return {
        "version": 2,
        "meta": {
            "sourceRunId": meta.get("sourceRunId"),
            "sourceGeneratedAt": meta.get("generatedAt"),
            "sourceSha256": hashlib.sha256(source_bytes).hexdigest(),
            "recordCount": meta.get("recordCount"),
            "canonicalKeyCount": len(keys),
            "expectedSamplesPerKey": meta.get("expectedSamplesPerKey"),
            "samplesPerPosition": 25,
            "positions": [1, 2, 3, 4],
            "isComplete": True,
        },
        "keys": keys,
    }


def main() -> None:
    args = _parser().parse_args()
    payload = build_lookup(args.input.resolve())
    output = args.output.resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(payload, ensure_ascii=True, separators=(",", ":"), sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(f"Built {output} ({len(payload['keys']):,} canonical keys).")


if __name__ == "__main__":
    main()
