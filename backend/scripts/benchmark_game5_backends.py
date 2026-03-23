import json
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "backend" / "scripts" / "benchmark_module_backends.py"
OUT_DIR = ROOT / "backend" / "data" / "bench_minimax_case"
MODULE = "app.scripts.minimax_benchmark_case"


def main():
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    proc = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--module",
            MODULE,
            "--out",
            str(OUT_DIR),
        ],
        cwd=ROOT,
        text=True,
        capture_output=True,
    )

    if proc.stdout:
        print(proc.stdout.strip())
    if proc.stderr:
        print(proc.stderr.strip())

    if proc.returncode != 0:
        raise SystemExit(proc.returncode)

    summary_path = OUT_DIR / "summary.json"
    if summary_path.exists():
        summary = json.loads(summary_path.read_text(encoding="utf-8"))
        print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
