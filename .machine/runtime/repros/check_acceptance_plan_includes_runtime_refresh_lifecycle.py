from __future__ import annotations

import json
import pathlib
import sys


REQUIRED_CMD = (
    "bash .machine/runtime/bin/pytest_cmd.sh "
    "tests/unit/test_api_stash_valuations.py::"
    "test_stash_scan_valuations_start_payload_exposes_refresh_lifecycle_metadata"
)


def main() -> int:
    plan_path = pathlib.Path(".machine/runtime/VerificationPlan.json")
    plan = json.loads(plan_path.read_text())
    commands = [
        cmd.strip()
        for cmd in plan.get("acceptance_gate_commands") or []
        if isinstance(cmd, str) and cmd.strip()
    ]
    if REQUIRED_CMD in commands:
        print("ACCEPTANCE_PLAN_RUNTIME_LIFECYCLE_CHECK_PRESENT")
        return 0
    print("ACCEPTANCE_PLAN_RUNTIME_LIFECYCLE_CHECK_MISSING")
    print(f"required_command={REQUIRED_CMD}")
    return 1


if __name__ == "__main__":
    sys.exit(main())
