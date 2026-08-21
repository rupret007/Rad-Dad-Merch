#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
import re
import sys
import zipfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
RELEASE = ROOT / "release" / "v6"
MANIFEST = RELEASE / "MANIFEST.json"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def main() -> int:
    if not MANIFEST.is_file():
        print(f"Missing manifest: {MANIFEST}", file=sys.stderr)
        return 1
    data = json.loads(MANIFEST.read_text(encoding="ascii"))
    errors: list[str] = []
    for item in data.get("files", []):
        path = ROOT / item["path"]
        if not path.is_file():
            errors.append(f"Missing: {item['path']}")
            continue
        if path.stat().st_size != item["bytes"]:
            errors.append(f"Size mismatch: {item['path']}")
        if sha256(path) != item["sha256"]:
            errors.append(f"Checksum mismatch: {item['path']}")
        if path.suffix.lower() == ".3mf":
            try:
                with zipfile.ZipFile(path) as archive:
                    names = set(archive.namelist())
                    if "3D/3dmodel.model" not in names:
                        errors.append(f"Invalid 3MF package: {item['path']}")
            except zipfile.BadZipFile:
                errors.append(f"Unreadable 3MF package: {item['path']}")
    qa_path = RELEASE / "qa" / "MODEL_QA_REPORT.txt"
    if not qa_path.is_file():
        errors.append("Missing digital model QA report")
    else:
        qa = qa_path.read_text(encoding="ascii")
        checks = {
            "watertight models": qa.count("Watertight: True") == 4,
            "single-body models": [int(value) for value in re.findall(r"Bodies: (\d+)", qa)] == [1, 1, 1, 1],
            "zero boundary edges": qa.count("Boundary edges: 0") == 4,
            "zero non-manifold edges": qa.count("Non-manifold edges: 0") == 4,
            "A1 Mini fit": "Fits A1 Mini XY: True" in qa,
        }
        errors.extend(f"QA gate failed: {name}" for name, passed in checks.items() if not passed)
    if errors:
        print("\n".join(errors), file=sys.stderr)
        return 1
    print(f"Verified {len(data.get('files', []))} release files.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
