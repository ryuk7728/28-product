import argparse
import json
import os
import subprocess
import sys
import time
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
BACKEND_DIR = ROOT / "backend"


def _env_with_backend(backend: str):
    env = os.environ.copy()
    env["APP_MINIMAX_BACKEND"] = backend
    env["RL428_MINIMAX_BACKEND"] = backend

    old_path = env.get("PYTHONPATH", "")
    backend_path = str(BACKEND_DIR)
    if backend_path not in old_path.split(os.pathsep):
        env["PYTHONPATH"] = backend_path + (os.pathsep + old_path if old_path else "")
    return env


def parse_moves(stdout_text: str):
    moves = []
    for raw_line in stdout_text.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        parts = line.rsplit(" ", 1)
        if len(parts) != 2:
            continue
        action_text, weight_text = parts
        try:
            weight = float(weight_text)
        except ValueError:
            continue

        if action_text.startswith("defaultdict(") or "FREQQ" in action_text:
            continue

        if action_text == "True":
            action = True
        elif action_text == "False":
            action = False
        elif "_" in action_text or " of " in action_text:
            action = action_text
        else:
            continue

        moves.append({"action": action, "weight": weight})
    return moves


def run_backend(module_name: str, backend: str):
    env = _env_with_backend(backend)

    backend_check = subprocess.run(
        [sys.executable, "-c", "import app.legacy.minimax as m; print(m._MINIMAX_BACKEND_ACTIVE)"],
        cwd=ROOT,
        env=env,
        text=True,
        capture_output=True,
    )
    active_backend = backend_check.stdout.strip()

    runner_code = (
        f"import importlib; m=importlib.import_module('{module_name}'); "
        "getattr(m, 'main')()"
    )
    start = time.perf_counter()
    proc = subprocess.run(
        [sys.executable, "-c", runner_code],
        cwd=ROOT,
        env=env,
        text=True,
        capture_output=True,
    )
    elapsed = time.perf_counter() - start

    return {
        "requested_backend": backend,
        "active_backend": active_backend,
        "return_code": proc.returncode,
        "elapsed_seconds": elapsed,
        "stdout": proc.stdout,
        "stderr": proc.stderr,
        "moves": parse_moves(proc.stdout),
    }


def compare_moves(py_moves, rust_moves):
    length_match = len(py_moves) == len(rust_moves)
    first_mismatch = None
    for idx, (pm, rm) in enumerate(zip(py_moves, rust_moves)):
        if pm["action"] != rm["action"]:
            first_mismatch = {
                "index": idx,
                "python_action": pm["action"],
                "rust_action": rm["action"],
            }
            break
    return {
        "length_match": length_match,
        "python_move_count": len(py_moves),
        "rust_move_count": len(rust_moves),
        "first_action_mismatch": first_mismatch,
        "all_actions_match": first_mismatch is None and length_match,
    }


def write_artifacts(out_dir: Path, run_info):
    backend = run_info["requested_backend"]
    (out_dir / f"{backend}_stdout.txt").write_text(run_info["stdout"], encoding="utf-8")
    (out_dir / f"{backend}_stderr.txt").write_text(run_info["stderr"], encoding="utf-8")
    (out_dir / f"{backend}_moves.json").write_text(
        json.dumps(run_info["moves"], indent=2), encoding="utf-8"
    )


def main():
    parser = argparse.ArgumentParser(
        description="Benchmark Python vs Rust minimax backend for a module."
    )
    parser.add_argument(
        "--module",
        default="app.scripts.minimax_benchmark_case",
        help="Module path, e.g. app.scripts.minimax_benchmark_case",
    )
    parser.add_argument(
        "--out",
        default=None,
        help="Output directory. Default: backend/data/bench_<module>",
    )
    args = parser.parse_args()

    module_slug = args.module.replace(".", "_")
    if args.out:
        out_dir = Path(args.out)
    else:
        out_dir = ROOT / "backend" / "data" / f"bench_{module_slug}"
    out_dir.mkdir(parents=True, exist_ok=True)

    python_run = run_backend(args.module, "python")
    rust_run = run_backend(args.module, "rust")

    write_artifacts(out_dir, python_run)
    write_artifacts(out_dir, rust_run)

    move_compare = compare_moves(python_run["moves"], rust_run["moves"])
    speedup = None
    if rust_run["elapsed_seconds"] > 0:
        speedup = python_run["elapsed_seconds"] / rust_run["elapsed_seconds"]

    summary = {
        "module": args.module,
        "python": {
            "requested_backend": python_run["requested_backend"],
            "active_backend": python_run["active_backend"],
            "return_code": python_run["return_code"],
            "elapsed_seconds": python_run["elapsed_seconds"],
        },
        "rust": {
            "requested_backend": rust_run["requested_backend"],
            "active_backend": rust_run["active_backend"],
            "return_code": rust_run["return_code"],
            "elapsed_seconds": rust_run["elapsed_seconds"],
        },
        "move_comparison": move_compare,
        "speedup_python_over_rust": speedup,
        "artifacts_dir": str(out_dir),
    }

    (out_dir / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(json.dumps(summary, indent=2))

    if python_run["return_code"] != 0 or rust_run["return_code"] != 0:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
