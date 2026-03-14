from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(".sisyphus/evidence/product")


def main() -> int:
    ROOT.mkdir(parents=True, exist_ok=True)
    files = sorted(path for path in ROOT.rglob("*") if path.is_file())
    index = {
        "artifactCount": len(files),
        "artifacts": [str(path) for path in files],
    }
    index_path = ROOT / "index.json"
    summary_path = ROOT / "summary.md"
    index_path.write_text(json.dumps(index, indent=2) + "\n", encoding="utf-8")

    lines = ["# Product Evidence Summary", "", f"- Artifact count: {len(files)}", ""]
    for path in files:
        lines.append(f"- `{path}`")
    summary_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
