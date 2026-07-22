#!/usr/bin/env python3
"""Pack Original CCTV videos for GitHub WITHOUT altering the source files.

CRITICAL (forensic):
- Never re-encode, transcode, resize, or rewrite Original/*.mp4|mkv
- Only create sidecar ZIP archives (ZIP_STORED = bit-exact payload) and
  split those archives into parts under --max-mb (default 95 MiB)
- SHA-256 of the original is recorded; unpack verifies byte-identical restore

Examples:
  python scripts/pack_original.py Original/ch07.mp4 Original/ch09.mp4
  python scripts/pack_original.py --unpack Original/packs/ch07.mp4
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import shutil
import sys
import zipfile
from pathlib import Path

DEFAULT_MAX_MB = 95
PART_DIGITS = 3


def sha256_file(path: Path, chunk: int = 1024 * 1024) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        while True:
            b = f.read(chunk)
            if not b:
                break
            h.update(b)
    return h.hexdigest()


def mb(n: int | float) -> float:
    return n / (1024 * 1024)


def split_file(src: Path, dest_dir: Path, stem: str, max_bytes: int) -> list[str]:
    """Split src into dest_dir/stem.part001, .part002, ... Return part filenames."""
    size = src.stat().st_size
    n_parts = max(1, math.ceil(size / max_bytes))
    parts: list[str] = []
    with src.open("rb") as f:
        for i in range(1, n_parts + 1):
            name = f"{stem}.part{i:0{PART_DIGITS}d}"
            out = dest_dir / name
            remaining = max_bytes if i < n_parts else size - max_bytes * (n_parts - 1)
            # last part: read the rest
            if i == n_parts:
                data = f.read()
            else:
                data = f.read(max_bytes)
            out.write_bytes(data)
            parts.append(name)
            print(f"  part {name}: {mb(len(data)):.2f} MiB")
    return parts


def join_parts(pack_dir: Path, parts: list[str], dest: Path) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    with dest.open("wb") as out:
        for name in parts:
            p = pack_dir / name
            if not p.exists():
                raise FileNotFoundError(f"Missing part: {p}")
            out.write(p.read_bytes())


def pack_one(src: Path, packs_root: Path, max_mb: float) -> Path:
    if not src.is_file():
        raise FileNotFoundError(src)

    max_bytes = int(max_mb * 1024 * 1024)
    digest = sha256_file(src)
    size = src.stat().st_size
    print(f"\n{src}: {mb(size):.2f} MiB | sha256={digest}")

    pack_dir = packs_root / src.name
    if pack_dir.exists():
        shutil.rmtree(pack_dir)
    pack_dir.mkdir(parents=True)

    # ZIP_STORED: no recompression — payload bytes identical to source
    zip_path = pack_dir / f"{src.name}.zip"
    print(f"  writing ZIP_STORED -> {zip_path.name} (source untouched)")
    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_STORED) as zf:
        zf.write(src, arcname=src.name)

    zip_size = zip_path.stat().st_size
    zip_sha = sha256_file(zip_path)
    print(f"  zip: {mb(zip_size):.2f} MiB")

    if zip_size <= max_bytes:
        parts = [zip_path.name]
        # keep single zip; no split
        print(f"  under {max_mb} MiB — no split needed")
    else:
        # split the zip (not the original) into parts
        stem = f"{src.name}.zip"
        tmp_zip = zip_path
        parts = split_file(tmp_zip, pack_dir, stem, max_bytes)
        tmp_zip.unlink()  # only keep parts
        print(f"  split into {len(parts)} parts (<= {max_mb} MiB each)")

    part_meta = []
    for name in parts:
        p = pack_dir / name
        part_meta.append(
            {
                "name": name,
                "size": p.stat().st_size,
                "sha256": sha256_file(p),
            }
        )
        if p.stat().st_size > max_bytes:
            raise RuntimeError(f"{name} still exceeds {max_mb} MiB")

    manifest = {
        "version": 1,
        "method": "zip-stored-split",
        "note": "Original CCTV file was NOT modified. Archive uses ZIP_STORED (bit-exact).",
        "original": {
            "name": src.name,
            "relative": str(src).replace("\\", "/"),
            "size": size,
            "sha256": digest,
        },
        "zip_sha256_before_split": zip_sha if len(parts) > 1 else part_meta[0]["sha256"],
        "max_mb": max_mb,
        "parts": part_meta,
    }
    man_path = pack_dir / "manifest.json"
    man_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    print(f"  manifest: {man_path}")
    print(f"  OK pack dir: {pack_dir}")
    return pack_dir


def unpack_one(pack_dir: Path, dest: Path | None, verify: bool = True) -> Path:
    man_path = pack_dir / "manifest.json"
    if not man_path.exists():
        raise FileNotFoundError(f"No manifest.json in {pack_dir}")
    man = json.loads(man_path.read_text(encoding="utf-8"))
    parts = [p["name"] for p in man["parts"]]
    original_name = man["original"]["name"]
    expected = man["original"]["sha256"]

    # Verify part hashes first
    for pmeta in man["parts"]:
        p = pack_dir / pmeta["name"]
        got = sha256_file(p)
        if got != pmeta["sha256"]:
            raise RuntimeError(f"Part corrupt: {p.name} sha256 mismatch")

    out = dest if dest else pack_dir.parent.parent / original_name
    # If packs are under Original/packs/<name>/, default restore to Original/<name>
    if dest is None:
        # pack_dir = Original/packs/ch07.mp4 -> Original/ch07.mp4
        out = pack_dir.parent.parent / original_name

    tmp_zip = pack_dir / "_rejoined.zip"
    try:
        if len(parts) == 1 and parts[0].endswith(".zip") and (pack_dir / parts[0]).exists():
            zip_path = pack_dir / parts[0]
        else:
            print(f"  joining {len(parts)} parts -> zip")
            join_parts(pack_dir, parts, tmp_zip)
            zip_path = tmp_zip

        print(f"  extracting ZIP_STORED -> {out}")
        out.parent.mkdir(parents=True, exist_ok=True)
        with zipfile.ZipFile(zip_path, "r") as zf:
            # extract only the expected member
            names = zf.namelist()
            if original_name not in names:
                # allow nested path
                member = next((n for n in names if Path(n).name == original_name), None)
                if not member:
                    raise RuntimeError(f"{original_name} not found in zip: {names}")
            else:
                member = original_name
            with zf.open(member) as src, out.open("wb") as dst:
                shutil.copyfileobj(src, dst)

        if verify:
            got = sha256_file(out)
            if got != expected:
                out.unlink(missing_ok=True)
                raise RuntimeError(
                    f"SHA-256 mismatch after unpack!\n  expected {expected}\n  got      {got}"
                )
            print(f"  verified sha256 OK: {got}")
        print(f"  restored: {out} ({mb(out.stat().st_size):.2f} MiB)")
        return out
    finally:
        if tmp_zip.exists():
            tmp_zip.unlink()


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Pack/unpack Original CCTV files for GitHub without tampering"
    )
    parser.add_argument(
        "inputs",
        nargs="*",
        type=Path,
        help="Videos to pack, or pack dirs when --unpack",
    )
    parser.add_argument("--max-mb", type=float, default=DEFAULT_MAX_MB)
    parser.add_argument(
        "--packs-dir",
        type=Path,
        default=None,
        help="Output root for packs (default: Original/packs)",
    )
    parser.add_argument(
        "--unpack",
        action="store_true",
        help="Unpack pack dir(s) and verify SHA-256",
    )
    parser.add_argument(
        "--dest",
        type=Path,
        default=None,
        help="Destination file when unpacking a single pack",
    )
    args = parser.parse_args()

    root = Path(__file__).resolve().parents[1]
    packs_root = args.packs_dir or (root / "Original" / "packs")

    if args.unpack:
        targets = args.inputs or sorted(p for p in packs_root.iterdir() if p.is_dir())
        if not targets:
            raise SystemExit("No pack dirs to unpack")
        for t in targets:
            pack_dir = t if t.is_absolute() else root / t
            if pack_dir.is_file() and pack_dir.name == "manifest.json":
                pack_dir = pack_dir.parent
            print(f"\nUnpack {pack_dir}")
            unpack_one(pack_dir, args.dest if len(targets) == 1 else None)
        return 0

    inputs = args.inputs
    if not inputs:
        inputs = [Path("Original/ch07.mp4"), Path("Original/ch09.mp4")]

    packs_root.mkdir(parents=True, exist_ok=True)
    done = []
    for item in inputs:
        src = item if item.is_absolute() else root / item
        done.append(pack_one(src, packs_root, args.max_mb))

    print("\nSummary (sources were NOT modified):")
    for d in done:
        parts = list(d.glob("*.part*")) + list(d.glob("*.zip"))
        for p in sorted(parts):
            print(f"  {p.relative_to(root)}  {mb(p.stat().st_size):.2f} MiB")
        print(f"  { (d / 'manifest.json').relative_to(root) }")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
