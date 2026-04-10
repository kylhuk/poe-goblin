#!/usr/bin/env python3
from __future__ import annotations

import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]


def main() -> int:
    if len(sys.argv) != 2 or sys.argv[1] not in {"test_matrix", "verify_plan"}:
        print("USAGE: runtime_plan_guard.py [test_matrix|verify_plan]")
        return 2

    target = sys.argv[1]
    script = (
        ".machine/runtime/test_matrix_guard.sh"
        if target == "test_matrix"
        else ".machine/runtime/verify_plan_guard.sh"
    )
    completed = subprocess.run(["bash", script], cwd=ROOT)
    return completed.returncode


if __name__ == "__main__":
    raise SystemExit(main())
