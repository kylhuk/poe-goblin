#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import cast


DEFAULT_REQUIRED_ARTIFACTS = [
    "task-1-baseline.json",
    "task-10-promotion-gates.json",
    "task-11-rollout-cutover.json",
    "task-11-rollout-rollback.json",
]

REQUIRED_JSON_KEYS: dict[str, tuple[str, ...]] = {
    "task-1-baseline.json": ("latency_ms", "p50_ms", "p95_ms", "corpus_hash"),
    "task-10-promotion-gates.json": (
        "status",
        "gate_results",
        "summary",
        "all_passed",
    ),
    "task-11-rollout-cutover.json": (
        "status",
        "rollout",
        "effectiveServingModelVersion",
        "lastAction",
    ),
    "task-11-rollout-rollback.json": (
        "status",
        "rollout",
        "effectiveServingModelVersion",
        "lastAction",
    ),
}


def _validate_artifact_semantics(
    rel_path: str, payload: dict[str, object]
) -> list[str]:
    errors: list[str] = []
    if rel_path == "task-10-promotion-gates.json":
        summary = payload.get("summary")
        if not isinstance(summary, dict):
            return ["task-10-promotion-gates.json:summary_not_object"]
        mdape_improvement = summary.get("mdape_relative_improvement")
        p95_improvement = summary.get("p95_latency_improvement_percent")
        cohort_degradation_count = summary.get("protected_cohort_degradation_count")
        if not isinstance(mdape_improvement, (int, float)):
            errors.append(
                "task-10-promotion-gates.json:mdape_relative_improvement_not_numeric"
            )
        elif float(mdape_improvement) < 0.2:
            errors.append(
                "task-10-promotion-gates.json:mdape_relative_improvement_below_threshold"
            )
        if not isinstance(p95_improvement, (int, float)):
            errors.append(
                "task-10-promotion-gates.json:p95_latency_improvement_not_numeric"
            )
        elif float(p95_improvement) < 50.0:
            errors.append(
                "task-10-promotion-gates.json:p95_latency_improvement_below_threshold"
            )
        if not isinstance(cohort_degradation_count, int):
            errors.append(
                "task-10-promotion-gates.json:protected_cohort_degradation_count_not_int"
            )
        elif cohort_degradation_count != 0:
            errors.append(
                "task-10-promotion-gates.json:protected_cohort_degradation_not_zero"
            )
        if payload.get("all_passed") is not True:
            errors.append("task-10-promotion-gates.json:all_passed_not_true")
        if summary.get("verdict") != "promote":
            errors.append("task-10-promotion-gates.json:verdict_not_promote")
    return errors


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(8192), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Verify required deterministic ML evidence artifacts and "
            "write a reproducible evidence-pack log."
        )
    )
    _ = parser.add_argument(
        "--evidence-root",
        default=".sisyphus/evidence",
        help="Directory that contains deterministic evidence artifacts.",
    )
    _ = parser.add_argument(
        "--output-log",
        default=".sisyphus/evidence/task-12-deterministic-pack.log",
        help="Path to write the deterministic evidence pack log.",
    )
    _ = parser.add_argument(
        "--required",
        nargs="+",
        default=DEFAULT_REQUIRED_ARTIFACTS,
        help=(
            "Relative artifact paths under --evidence-root that are required "
            "for deterministic ML verification."
        ),
    )
    return parser


def main() -> int:
    parser = _build_parser()
    args = cast(argparse.Namespace, parser.parse_args())

    evidence_root = Path(str(args.evidence_root))
    output_log = Path(str(args.output_log))
    raw_required = [str(item) for item in cast(list[object], args.required)]
    required = sorted(set(raw_required))

    missing: list[str] = []
    invalid: list[str] = []
    present_entries: list[dict[str, object]] = []
    for rel_path in required:
        artifact_path = evidence_root / rel_path
        if not artifact_path.exists() or not artifact_path.is_file():
            missing.append(rel_path)
            continue
        json_keys = REQUIRED_JSON_KEYS.get(rel_path)
        if json_keys is not None:
            try:
                parsed = json.loads(artifact_path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                invalid.append(f"{rel_path}:invalid_json")
                continue
            if not isinstance(parsed, dict):
                invalid.append(f"{rel_path}:not_object")
                continue
            missing_keys = [key for key in json_keys if key not in parsed]
            if missing_keys:
                invalid.append(f"{rel_path}:missing_keys({','.join(missing_keys)})")
                continue
            invalid.extend(_validate_artifact_semantics(rel_path, parsed))
            if invalid and any(entry.startswith(f"{rel_path}:") for entry in invalid):
                continue
        present_entries.append(
            {
                "artifact": rel_path,
                "bytes": artifact_path.stat().st_size,
                "sha256": _sha256(artifact_path),
            }
        )

    payload: dict[str, object] = {
        "evidence_root": str(evidence_root),
        "required_artifacts": required,
        "present": present_entries,
        "missing": missing,
        "invalid": invalid,
        "status": "ok"
        if not missing and not invalid
        else "missing_or_invalid_artifacts",
    }

    output_log.parent.mkdir(parents=True, exist_ok=True)
    _ = output_log.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )

    if missing or invalid:
        missing_csv = ", ".join(missing)
        invalid_csv = ", ".join(invalid)
        details = []
        if missing_csv:
            details.append(f"missing required artifact(s): {missing_csv}")
        if invalid_csv:
            details.append(f"invalid artifact payload(s): {invalid_csv}")
        message = (
            "ERROR: deterministic ML evidence verification failed; "
            + "; ".join(details)
            + f". See {output_log} for details."
        )
        print(message)
        return 1

    print(f"deterministic ML evidence verification passed; wrote {output_log}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
