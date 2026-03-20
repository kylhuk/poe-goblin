#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path
from typing import Sequence

from poe_trade.ml import workflows

SETTINGS_TO_CHECK: Sequence[str] = (
    "max_memory_usage",
    "max_threads",
    "max_execution_time",
    "max_bytes_before_external_group_by",
    "max_bytes_before_external_sort",
)


def main() -> int:
    sql_settings = workflows._mod_feature_sql_query_settings()
    result = {name: sql_settings.get(name, "") for name in SETTINGS_TO_CHECK}
    output_path = Path(".sisyphus/evidence/task-7-settings-active.txt")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"Wrote active settings evidence to {output_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
