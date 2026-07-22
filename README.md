# CCTV Video Restoration

Pipeline to restore / enhance CCTV footage with **VRT** (Video Restoration Transformer).

## Forensic rule for `Original/`

**CCTV sources must never be re-encoded, resized, or rewritten** for GitHub size limits.  
If a file is over ~100 MB, pack it with **ZIP_STORED + split parts** (`scripts/pack_original.py`). The original bytes stay on disk; SHA-256 is verified on unpack.

## What’s in the repo

| Path | Purpose |
|------|---------|
| `Original/` | Source CCTV (bit-exact; do not tamper) |
| `Original/packs/` | GitHub-safe ZIP_STORED split archives (≤95 MiB each part) |
| `Restored/` | VRT outputs (gitignored) |
| `scripts/pack_original.py` | Pack / unpack without altering sources |
| `scripts/restore_cctv.py` | Local VRT restore entrypoint |
| `.cursor/skills/vrt-video-restoration/` | VRT agent skill (denoise/deblur) |
| `.cursor/skills/realesrgan/` | Real-ESRGAN skill (faces/plates upscale) |
| `tools/realesgan/` | Portable Real-ESRGAN ncnn-vulkan |
| `tools/VRT/` | Official VRT clone (gitignored) |

## Requirements

- Python 3.10+
- FFmpeg on `PATH` (`winget install Gyan.FFmpeg`) — for restore only, not for packing
- CUDA GPU recommended for VRT

```bash
pip install torch torchvision --index-url https://download.pytorch.org/whl/cu124
git clone --depth 1 https://github.com/JingyunLiang/VRT tools/VRT
pip install -r tools/VRT/requirements.txt matplotlib
```

## Pack Original videos for GitHub (no tampering)

```bash
# Pack ch07 + ch09 into Original/packs/<name>/ (parts <= 95 MiB)
python scripts/pack_original.py Original/ch07.mp4 Original/ch09.mp4

# Restore + verify SHA-256 (byte-identical)
python scripts/pack_original.py --unpack Original/packs/ch07.mp4
python scripts/pack_original.py --unpack
```

| File | Git policy |
|------|------------|
| `Original/ch07.mp4` (~174 MiB) | **gitignored** — commit `Original/packs/ch07.mp4/*` only |
| `Original/ch09.mp4` (~50 MiB) | Can commit as-is **or** pack; packing still recommended for consistency |
| Pack parts / `manifest.json` | Commit these (each part &lt; 100 MB) |

**Forbidden:** ffmpeg re-encode, CRF, bitrate targets, or “compress video” on evidence footage.

## Restore with VRT

```bash
python scripts/restore_cctv.py --input Original/CUT/cut.mkv
```

See `.cursor/skills/vrt-video-restoration/SKILL.md`. For face/plate upscale, see `.cursor/skills/realesrgan/SKILL.md` (small-frame bakeoff first).

## Citation (VRT)

```
@article{liang2022vrt,
  title={VRT: A Video Restoration Transformer},
  author={Liang, Jingyun and Cao, Jiezhang and Fan, Yuchen and Zhang, Kai and Ranjan, Rakesh and Li, Yawei and Timofte, Radu and Van Gool, Luc},
  journal={arXiv preprint arXiv:2201.12288},
  year={2022}
}
```

VRT is CC-BY-NC. See [JingyunLiang/VRT](https://github.com/JingyunLiang/VRT).
