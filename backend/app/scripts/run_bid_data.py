from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import sys


POLICIES = {
    "baseline": [3, 3, 4, 4, 4, 3, 2, 1],
    "option_a": [2, 2, 3, 3, 4, 3, 2, 1],
}


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run deterministic, headless Rust bid-data samples."
    )
    key = parser.add_mutually_exclusive_group()
    key.add_argument("--key-index", type=int)
    key.add_argument("--canonical-key-id")
    parser.add_argument("--sample-index", type=int, default=0)
    parser.add_argument("--count", type=int, default=1)
    parser.add_argument("--root-seed")
    parser.add_argument("--run-id")
    parser.add_argument("--policy", choices=sorted(POLICIES), default="baseline")
    parser.add_argument("--workers", type=int, default=8)
    parser.add_argument(
        "--samples-per-task",
        type=int,
        default=None,
        help="Map CLOUD_RUN_TASK_INDEX across fixed-size sample shards.",
    )
    parser.add_argument(
        "--gcs-output-prefix",
        default=None,
        help="Immutable GCS shard prefix, for example gs://bucket/raw.",
    )
    parser.add_argument(
        "--output",
        default="-",
        help="NDJSON output path, or '-' for stdout.",
    )
    return parser


def _configure_environment(policy: str, workers: int) -> None:
    values = POLICIES[policy]
    os.environ["APP_MINIMAX_BACKEND"] = "rust"
    os.environ["APP_MINIMAX_STRICT_RUST"] = "1"
    os.environ["APP_ROLLOUT_BACKEND"] = "local"
    os.environ["APP_ROLLOUTS"] = "500"
    os.environ["APP_WORKERS"] = str(workers)
    os.environ["APP_K_OVERRIDE"] = ""
    os.environ["APP_K_BY_CATCH"] = ",".join(
        f"{catch}:{value}" for catch, value in enumerate(values, start=1)
    )
    os.environ["APP_BOT_THINK_TIMEOUT_SECONDS"] = "0"


def _write_rows(rows: list[dict], output: str) -> None:
    lines = [json.dumps(row, ensure_ascii=True, separators=(",", ":")) for row in rows]
    if output == "-":
        for line in lines:
            print(line)
        return

    path = Path(output)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8", newline="\n") as stream:
        for line in lines:
            stream.write(line)
            stream.write("\n")


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    if args.count <= 0:
        raise SystemExit("--count must be positive")
    if args.workers <= 0:
        raise SystemExit("--workers must be positive")
    if args.sample_index < 0 or args.sample_index + args.count > 100:
        raise SystemExit("requested sample range must stay within 0..99")

    key_index = args.key_index
    sample_index = args.sample_index
    count = args.count
    if key_index is None and args.canonical_key_id is None:
        task_index = os.getenv("CLOUD_RUN_TASK_INDEX")
        if task_index is None:
            raise SystemExit(
                "provide --key-index/--canonical-key-id or CLOUD_RUN_TASK_INDEX"
            )
        task_index_value = int(task_index)
        samples_per_task = args.samples_per_task or int(
            os.getenv("APP_SAMPLES_PER_TASK", "25")
        )
        if samples_per_task <= 0 or 100 % samples_per_task != 0:
            raise SystemExit("samples per task must be a positive divisor of 100")
        blocks_per_key = 100 // samples_per_task
        key_index = task_index_value // blocks_per_key
        sample_index = (task_index_value % blocks_per_key) * samples_per_task
        count = samples_per_task
    root_seed = args.root_seed or os.getenv("APP_ROOT_SEED")
    if not root_seed:
        raise SystemExit("provide --root-seed or APP_ROOT_SEED")
    run_id = args.run_id or os.getenv("APP_RUN_ID", "local-phase-2")

    _configure_environment(args.policy, args.workers)

    # Imports are intentionally delayed until the strict Rust environment is set.
    from app.experiments.bid_data_v1 import (
        build_sample_request,
        simulate_requests_sync,
    )

    requests = [
        build_sample_request(
            canonical_key_id=args.canonical_key_id,
            key_index=key_index,
            sample_index=current_sample_index,
            root_seed=root_seed,
            policy_name=args.policy,
            run_id=run_id,
        )
        for current_sample_index in range(sample_index, sample_index + count)
    ]

    gcs_prefix = args.gcs_output_prefix or os.getenv("APP_GCS_OUTPUT_PREFIX")
    if gcs_prefix:
        from app.experiments.bid_data_v1 import catalog_entry_by_id
        from app.experiments.gcs_results import GcsShardStore, shard_object_name

        entry = catalog_entry_by_id(requests[0].canonical_key_id)
        policy_id = (
            "k-baseline-33444321-r500"
            if args.policy == "baseline"
            else "k-option-a-22334321-r500"
        )
        store = GcsShardStore(gcs_prefix)
        object_name = shard_object_name(
            prefix=store.location.prefix,
            run_id=run_id,
            policy_id=policy_id,
            key_index=entry.index,
            canonical_key_id=entry.canonical_key_id,
            sample_start=sample_index,
            sample_count=count,
        )
        if store.exists(object_name):
            print(json.dumps({"status": "SKIPPED_EXISTING", "object": object_name}))
            return 0
        rows = simulate_requests_sync(requests)
        print(json.dumps(store.upload_immutable(object_name, rows), separators=(",", ":")))
    else:
        rows = simulate_requests_sync(requests)
        _write_rows(rows, args.output)
    return 0


if __name__ == "__main__":
    sys.exit(main())
