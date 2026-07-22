#!/usr/bin/env python3
"""One-time migration: *-bakeoff folders -> work/datasets + work/labs."""

from __future__ import annotations

import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WORK = ROOT / "work"

MIGRATIONS = [
    {
        "legacy": WORK / "cut2-bakeoff",
        "dataset": "cut2",
        "lab": "lab-001-historical-upscayl",
        "dataset_dirs": ["src", "crops"],
        "lab_dirs": ["outputs", "rvrt_in"],
        "lab_files": ["RESULTS.md"],
    },
    {
        "legacy": WORK / "cut-motor-2308-bakeoff",
        "dataset": "cut-motor-2308",
        "lab": "lab-001-classified-v2",
        "dataset_dirs": ["src", "full", "crops"],
        "dataset_files": ["meta.json"],
        "lab_dirs": ["outputs", "intermediate", "rvrt_in"],
        "lab_files": ["RESULTS.md"],
    },
]


def move_contents(src: Path, dst: Path) -> None:
    if not src.exists():
        return
    dst.mkdir(parents=True, exist_ok=True)
    for item in src.iterdir():
        target = dst / item.name
        if target.exists():
            print(f"skip exists {target}")
            continue
        shutil.move(str(item), str(target))
        print(f"moved {item} -> {target}")


def main() -> int:
    for spec in MIGRATIONS:
        legacy = spec["legacy"]
        if not legacy.exists():
            print(f"skip missing {legacy}")
            continue

        ds_root = WORK / "datasets" / spec["dataset"]
        lab_root = WORK / "labs" / spec["dataset"] / spec["lab"]

        for name in spec.get("dataset_dirs", []):
            move_contents(legacy / name, ds_root / name)
        for name in spec.get("dataset_files", []):
            src = legacy / name
            if src.exists() and not (ds_root / name).exists():
                ds_root.mkdir(parents=True, exist_ok=True)
                shutil.move(str(src), str(ds_root / name))
                print(f"moved {src} -> {ds_root / name}")

        for name in spec.get("lab_dirs", []):
            move_contents(legacy / name, lab_root / name)
        for name in spec.get("lab_files", []):
            src = legacy / name
            if src.exists() and not (lab_root / name).exists():
                lab_root.mkdir(parents=True, exist_ok=True)
                shutil.move(str(src), str(lab_root / name))
                print(f"moved {src} -> {lab_root / name}")

        # Stub pointer in legacy path
        if legacy.exists() and not any(legacy.iterdir()):
            legacy.rmdir()
        stub = legacy
        if not stub.exists():
            stub.mkdir(parents=True, exist_ok=True)
        readme = stub / "README.md"
        if not readme.exists():
            readme.write_text(
                f"# Moved\n\n"
                f"- **Source frames:** `work/datasets/{spec['dataset']}/`\n"
                f"- **This lab:** `work/labs/{spec['dataset']}/{spec['lab']}/`\n"
                f"- **New labs:** `python scripts/bakeoff_hybrid.py --dataset {spec['dataset']} --new-lab \"description\"`\n",
                encoding="utf-8",
            )
            print(f"wrote {readme}")

    print("Done. See work/README.md")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
