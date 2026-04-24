"""
Run all OnCourt extractions (Phase 1.1a + 1.1b + 1.1c).
Run: C:\\Python312-32\\python.exe scripts/oncourt-extract-all.py

Set: $env:ONCOURT_PWD="your_password"
"""

import subprocess
import sys
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parent
PY = r"C:\Python312-32\python.exe"

def main():
    if not Path(PY).exists():
        print(f"32-bit Python not found at {PY}")
        sys.exit(1)

    # Rest first: games need the latest tours_atp.csv to backfill tour dates.
    for name in ["oncourt-extract-rest", "oncourt-extract-games", "oncourt-extract-stats"]:
        script = SCRIPTS / f"{name}.py"
        if not script.exists():
            print(f"Missing {script}")
            return 1
        print(f"\n--- {name} ---")
        subprocess.run([PY, str(script)], check=True)

    print("\nAll extractions done.")


if __name__ == "__main__":
    main()
