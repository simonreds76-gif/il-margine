"""
Run all OnCourt extractions (Phase 1.1a + 1.1b + 1.1c).
Run: C:\\Python312-32\\python.exe scripts/oncourt-extract-all.py

Set: $env:ONCOURT_PWD="your_password"
"""

import os
import subprocess
import sys
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parent
PY = r"C:\Python312-32\python.exe"
DEFAULT_STEP_TIMEOUT_SECONDS = 1200


def _step_timeout_seconds() -> int:
    raw = os.environ.get("ONCOURT_EXTRACT_STEP_TIMEOUT_SECONDS", "").strip()
    if not raw:
        return DEFAULT_STEP_TIMEOUT_SECONDS
    try:
        value = int(raw)
    except ValueError:
        return DEFAULT_STEP_TIMEOUT_SECONDS
    return value if value > 0 else DEFAULT_STEP_TIMEOUT_SECONDS


def _run_extract_step(script: Path, timeout_seconds: int) -> int:
    try:
        subprocess.run([PY, str(script)], check=True, timeout=timeout_seconds)
        return 0
    except subprocess.TimeoutExpired:
        print(f"ERROR: {script.name} timed out after {timeout_seconds}s.", flush=True)
        return 124
    except subprocess.CalledProcessError as exc:
        print(f"ERROR: {script.name} failed with exit {exc.returncode}.", flush=True)
        return int(exc.returncode or 1)

def main():
    if not Path(PY).exists():
        print(f"32-bit Python not found at {PY}")
        sys.exit(1)

    timeout_seconds = _step_timeout_seconds()

    # Rest first: games need the latest tours_atp.csv to backfill tour dates.
    for name in ["oncourt-extract-rest", "oncourt-extract-games", "oncourt-extract-stats"]:
        script = SCRIPTS / f"{name}.py"
        if not script.exists():
            print(f"Missing {script}")
            return 1
        print(f"\n--- {name} ---", flush=True)
        exit_code = _run_extract_step(script, timeout_seconds)
        if exit_code != 0:
            return exit_code

    print("\nAll extractions done.", flush=True)


if __name__ == "__main__":
    raise SystemExit(main())
